from __future__ import annotations

import json
import os
import re
from dataclasses import asdict
from pathlib import Path
from statistics import mean, median
from unittest.mock import patch

from scripts.run_benchmark_20 import TESTS, evaluate
from src.generation import LendLensGenerator
from src.generation_providers import GroqProvider, OllamaProvider
from src.service import LendLensService
from tests import test_api_smoke


REPORTS = Path(__file__).resolve().parents[1] / "reports"
MODELS = (
    ("qwen3_4b", OllamaProvider()),
    ("groq_qwen38", GroqProvider()),
)
SMOKE = (
    test_api_smoke.test_rbi_cdd,
    test_api_smoke.test_tata_grievance,
    test_api_smoke.test_iifl_grievance,
    test_api_smoke.test_unanswerable,
    test_api_smoke.test_prompt_injection,
    test_api_smoke.test_lending_decision_guardrail,
)


def smoke_cases():
    for check in SMOKE:
        with patch.object(test_api_smoke, "ask") as ask:
            ask.side_effect = AssertionError("capture question")
            try:
                check()
            except AssertionError:
                question = ask.call_args.args[0]
        yield {"name": check.__name__, "question": question}, check


def evaluate_smoke(check, data):
    with patch.object(test_api_smoke, "ask", return_value=data):
        try:
            check()
        except AssertionError:
            return False, [{"check": check.__name__, "passed": False}]
    return True, [{"check": check.__name__, "passed": True}]


def run_suite(service, generators, cases, prepared_cache):
    results = {slug: [] for slug in generators}
    for index, (test, check) in enumerate(cases):
        question = test["question"]
        if question not in prepared_cache:
            prepared_cache[question] = service.prepare(question)
        prepared = prepared_cache[question]
        order = list(generators)
        # Rotate execution order across cases.
        offset = index % len(order)
        for slug in order[offset:] + order[:offset]:
            row = {"name": test["name"], "question": question}
            try:
                data, generation = service.answer_prepared(prepared, generators[slug])
                passed, checks = (
                    evaluate_smoke(check, data) if check else evaluate(test, data)
                )
                ids = {source["id"] for source in data["sources"]}
                cited = set(re.findall(r"\[(S\d+)\]", data["answer"]))
                raw_valid = generation.citation_ids_valid if generation else None
                if data["abstained"]:
                    citations_valid = not ids and not cited and raw_valid is not False
                else:
                    citations_valid = bool(cited) and cited <= ids and raw_valid is True
                metadata = asdict(generation) if generation else None
                if metadata:
                    metadata.pop("answer")
                row.update(
                    passed=passed, checks=checks, answer=data["answer"],
                    abstained=data["abstained"], blocked=data["blocked"],
                    routing=data["routing"], source_ids=sorted(ids),
                    citation_source_valid=citations_valid,
                    latency_seconds=data["latency_seconds"], generation=metadata,
                )
            except Exception as exc:
                from src.generation_providers import ProviderError
                error = str(exc) if isinstance(exc, ProviderError) else type(exc).__name__
                row.update(passed=False, error=error)
            results[slug].append(row)
            status = (
                "ERROR" if row.get("error")
                else "PASS" if row["passed"]
                else "FAIL"
            )
            print(slug, test["name"], status, flush=True)
    return results


def summarize(rows):
    calls = [row["generation"] for row in rows if row.get("generation")]
    totals = [row["latency_seconds"] for row in rows if "latency_seconds" in row]
    costs = [call["estimated_cost_usd"] for call in calls
             if call["generation_latency_seconds"] is not None]
    cost = sum(costs) / len(rows) if costs and len(totals) == len(rows) and all(
        value is not None for value in costs
    ) else None

    def metric(key, aggregate):
        values = [call[key] for call in calls if call[key] is not None]
        return round(aggregate(values), 3) if values else None

    return {
        "passed": sum(row["passed"] for row in rows),
        "total": len(rows),
        "median_generation_seconds": metric("generation_latency_seconds", median),
        "median_total_seconds": round(median(totals), 3) if totals else None,
        "average_input_tokens": metric("input_tokens", mean),
        "average_output_tokens": metric("output_tokens", mean),
        "cost_per_request_usd": cost,
        "cost_per_1000_usd": cost * 1000 if cost is not None else None,
        "citation_source_valid_cases": sum(row.get("citation_source_valid", False) for row in rows),
        "results": rows,
    }


def write_json(filename, data):
    (REPORTS / filename).write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def score(summary):
    return f"{summary['passed']}/{summary['total']}" if summary else "N/A"


def display(value):
    return "N/A" if value is None else f"{value:.6g}"


def write_markdown(models):
    comparison = ["# Six-case generator comparison", ""]
    tradeoff = [
        "# Generator tradeoffs", "",
        "| Model | Provider | 6-case score | 20-case score | Median generation (s) | Median total (s) | Avg input tokens | Avg output tokens | USD/request | USD/1,000 | Main strength | Main weakness |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for model in models.values():
        six = model.get("six_case")
        twenty = model.get("twenty_case")
        comparison.extend([f"## {model['model']}", "", model["status"], ""])
        if six:
            comparison.extend([f"Score **{score(six)}**", ""])
            for row in six["results"]:
                label = "PASS" if row["passed"] else "FAIL"
                comparison.extend([
                    f"### {row['question']}", "",
                    f"{label}. Citation/source IDs valid: {row.get('citation_source_valid', 'N/A')}.",
                    "", row.get("answer", row.get("error", "")), "",
                ])
        metrics = [display((six or {}).get(key)) for key in (
            "median_generation_seconds", "median_total_seconds", "average_input_tokens",
            "average_output_tokens", "cost_per_request_usd", "cost_per_1000_usd",
        )]
        if six:
            strength = f"{six['passed']}/{six['total']} smoke expectations met"
            weakness = f"{six['total'] - six['citation_source_valid_cases']} cases failed citation/source validation"
            if twenty:
                weakness += f"; {twenty['total'] - twenty['passed']} broader behavioral misses"
        else:
            strength, weakness = "Unmeasured", model["status"]
        values = [model["model"], model["provider"], score(six), score(twenty),
                  *metrics, strength, weakness]
        tradeoff.append("| " + " | ".join(values) + " |")
    tradeoff.extend([
        "", "Metrics in the table use the six-case run. Total service time includes shared",
        "preparation and each model's own generation/post-processing. Generation medians",
        "and token means exclude cases without a model call. Cost is API fees only;",
        "paid estimates use standard uncached rates and include zero-cost guardrail cases.",
        "Citation/source validation checks source IDs and abstention consistency. It does",
        "not establish factual entailment. All generators receive the same serialized",
        "evidence. Ollama retains its production 4,096-token context limit.", "",
        "Retain the current production default unless a tested alternative demonstrates",
        "an acceptable combination of behavioral score, grounding, latency, and cost.",
    ])
    for name, lines in (
        ("qwen4b_vs_groq_qwen38_6.md", comparison),
        ("qwen4b_vs_groq_qwen38_tradeoff.md", tradeoff),
    ):
        (REPORTS / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    REPORTS.mkdir(exist_ok=True)
    service = LendLensService()
    models, generators, prepared_cache = {}, {}, {}
    for slug, provider in MODELS:
        key_env = getattr(provider, "key_env", None)
        missing = key_env and not os.getenv(key_env)
        models[slug] = {
            "model": provider.model, "provider": provider.name,
            "status": f"Skipped: missing {key_env}" if missing else "Available",
        }
        if not missing:
            generators[slug] = LendLensGenerator(provider=provider)

    six = run_suite(service, generators, list(smoke_cases()), prepared_cache)
    eligible = {}
    for slug, rows in six.items():
        summary = summarize(rows)
        models[slug]["six_case"] = summary
        models[slug]["status"] = "Run completed" if not any(
            "error" in row for row in rows
        ) else "Run completed with request errors"
        if summary["passed"] >= 5:
            eligible[slug] = generators[slug]

    write_json("qwen4b_vs_groq_qwen38_6.json", models)
    write_markdown(models)
    if False and eligible:
        twenty = run_suite(service, eligible, [(test, None) for test in TESTS], prepared_cache)
        for slug, rows in twenty.items():
            summary = summarize(rows)
            models[slug]["twenty_case"] = summary
            write_json(f"benchmark_20_{slug}.json", {
                "model": models[slug]["model"], "provider": models[slug]["provider"], **summary,
            })
        write_markdown(models)


if __name__ == "__main__":
    main()
