from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, median
from time import perf_counter

import requests


API = "http://127.0.0.1:8000/ask"
REPORT = Path(__file__).resolve().parents[1] / "reports" / "latency_profile.json"
QUESTIONS = (
    "What documents must an NBFC obtain when performing CDD for an individual?",
    "Within how many days should Tata Capital respond to a customer grievance?",
    "What is Tata Capital's CEO's favorite food?",
)
STAGES = {
    "http_total": "Total latency (HTTP)",
    "service_total": "Total service latency",
    "guardrail": "Guardrail",
    "routing": "Routing",
    "dense_embedding": "Dense embedding",
    "sparse_embedding": "Sparse/BM25 embedding",
    "qdrant_retrieval": "Qdrant retrieval",
    "reranking": "Reranking",
    "context_expansion": "Context expansion",
    "retrieval_total": "Total retrieval",
    "prompt_construction": "Evidence/prompt construction",
    "generation": "Generation",
    "post_processing": "Post-processing",
}


def main() -> None:
    cases = []
    with requests.Session() as session:
        for question in QUESTIONS:
            started = perf_counter()
            response = session.post(API, json={"question": question}, timeout=180)
            http_total = round(perf_counter() - started, 3)
            response.raise_for_status()
            result = response.json()
            timings = {"http_total": http_total, **result["timings"]}
            cases.append({
                "question": question,
                "answer": result["answer"],
                "abstained": result["abstained"],
                "blocked": result["blocked"],
                "timings": {stage: timings.get(stage) for stage in STAGES},
            })
            print(f"Question: {question}")
            print(f"Answer: {result['answer']}")
            for stage, label in STAGES.items():
                value = timings.get(stage)
                display = f"{value:.3f} s" if value is not None else "N/A"
                print(f"{label}: {display}")
            print(flush=True)

    summary = {}
    for stage in STAGES:
        values = [case["timings"][stage] for case in cases]
        executed = [value for value in values if value is not None]
        summary[stage] = {
            "count": len(executed),
            "mean": round(mean(executed), 3) if executed else None,
            "median": round(median(executed), 3) if executed else None,
        }

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        json.dumps({"units": "seconds", "cases": cases, "summary": summary}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(f"Saved {REPORT}")


if __name__ == "__main__":
    main()
