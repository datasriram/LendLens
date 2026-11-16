from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import requests

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "evaluation" / "gold40" / "LendLens_Evaluation_Benchmark_v3_Gold40_Verified.xlsx"
OUTPUT = ROOT / "reports" / "gold40_raw_results.json"

API_BASE = os.getenv(
    "LENDLENS_API_URL", "http://127.0.0.1:8000"
).rstrip("/")
API = API_BASE if API_BASE.endswith("/ask") else API_BASE + "/ask"

M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def load_gold_questions():
    with ZipFile(WORKBOOK) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = [
                "".join(t.text or "" for t in si.iter(M + "t"))
                for si in root.findall(M + "si")
            ]

        book = ET.fromstring(z.read("xl/workbook.xml"))
        relroot = ET.fromstring(
            z.read("xl/_rels/workbook.xml.rels")
        )
        targets = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in relroot
        }

        sheet = next(
            s for s in book.iter(M + "sheet")
            if s.attrib["name"] == "Gold_40"
        )
        target = targets[sheet.attrib[R + "id"]]

        if target.startswith("/"):
            sheet_path = target.lstrip("/")
        else:
            sheet_path = "xl/" + target

        root = ET.fromstring(z.read(sheet_path))
        rows = []

        for row in root.findall(
            ".//" + M + "sheetData/" + M + "row"
        ):
            values = {}

            for cell in row.findall(M + "c"):
                ref = cell.attrib["r"]
                column = re.match(r"[A-Z]+", ref).group()
                typ = cell.attrib.get("t")
                value_node = cell.find(M + "v")

                if typ == "inlineStr":
                    value = "".join(
                        t.text or ""
                        for t in cell.iter(M + "t")
                    )
                elif value_node is not None:
                    value = value_node.text or ""
                    if typ == "s":
                        value = shared[int(value)]
                else:
                    value = ""

                values[column] = value.strip()

            rows.append(values)

    header = next(
        row for row in rows
        if row.get("B") == "Question ID"
        and row.get("E") == "Question"
    )

    questions = []

    for row in rows:
        qid = row.get("B", "")
        if not re.fullmatch(r"LL-\d{3}", qid):
            continue

        record = {
            header.get(column, column): value
            for column, value in row.items()
            if column in header
        }
        questions.append(record)

    ids = [q["Question ID"] for q in questions]

    if len(questions) != 40 or len(set(ids)) != 40:
        raise ValueError(
            "Expected exactly 40 unique gold questions; "
            f"found {len(questions)} rows and "
            f"{len(set(ids))} unique IDs."
        )

    return questions


def load_previous():
    if not OUTPUT.exists():
        return {}

    data = json.loads(OUTPUT.read_text(encoding="utf-8"))
    return data.get("results", {})


def save_results(results, gold_ids):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    completed = sum(
        1 for item in results.values()
        if item.get("status") == "completed"
    )
    errors = sum(
        1 for item in results.values()
        if item.get("status") == "error"
    )

    report = {
        "benchmark": "LendLens Gold-40 validation",
        "evaluation_type": "raw responses; not yet human-scored",
        "api": API,
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "total_gold_questions": len(gold_ids),
        "completed": completed,
        "errors": errors,
        "remaining": len(gold_ids) - completed,
        "results": results,
    }

    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(OUTPUT)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Maximum new attempts this run; default 3",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Attempt all unfinished questions",
    )
    args = parser.parse_args()

    questions = load_gold_questions()
    gold_ids = [q["Question ID"] for q in questions]
    results = load_previous()

    print("=" * 65)
    print("LENDLENS — GOLD-40 VALIDATION")
    print("=" * 65)
    print("Gold questions:", len(questions))
    print("API:", API)
    print("Saved results:", OUTPUT)
    print(
        "Previously completed:",
        sum(
            x.get("status") == "completed"
            for x in results.values()
        ),
    )

    session = requests.Session()
    attempts = 0

    for index, gold in enumerate(questions, 1):
        qid = gold["Question ID"]

        if results.get(qid, {}).get("status") == "completed":
            print(f"[{index:02d}/40] {qid}: SKIPPED (saved)")
            continue

        if not args.all and attempts >= args.limit:
            break

        question = gold["Question"]
        attempts += 1

        print(f"\n[{index:02d}/40] {qid}")
        print("Question:", question)

        started = time.perf_counter()

        try:
            response = session.post(
                API,
                json={"question": question},
                timeout=180,
            )

            response.raise_for_status()
            data = response.json()

            if not isinstance(data, dict):
                raise ValueError(
                    "API response is not a JSON object."
                )

            if "answer" not in data:
                raise ValueError(
                    "API response is missing the answer field."
                )

            record = {
                "question_id": qid,
                "status": "completed",
                "category": gold.get("Category"),
                "question": question,
                "gold": {
                    "should_answer": gold.get("Should Answer?"),
                    "expected_authority": gold.get(
                        "Expected Authority"
                    ),
                    "expected_source": gold.get(
                        "Expected Source / Document Family"
                    ),
                    "verified_answer": gold.get(
                        "Gold Answer (Verified)"
                    ),
                    "required_facts": gold.get(
                        "Must-Contain Facts"
                    ),
                    "page_clause": gold.get(
                        "Gold Page / Clause"
                    ),
                    "temporal_notes": gold.get(
                        "Temporal / Version Notes"
                    ),
                    "reviewer_notes": gold.get("Reviewer Notes"),
                    "source_urls": gold.get("Source URL(s)"),
                },
                "response": data,
                "wall_seconds": round(
                    time.perf_counter() - started, 3
                ),
            }

            results[qid] = record
            save_results(results, gold_ids)

            print("STATUS: COMPLETED")
            print("Abstained:", data.get("abstained"))
            print("Sources:", len(data.get("sources") or []))
            print("Latency:", data.get("latency_seconds"))
            print("Answer:", str(data.get("answer", ""))[:600])

        except Exception as exc:
            results[qid] = {
                "question_id": qid,
                "status": "error",
                "question": question,
                "error": str(exc),
                "wall_seconds": round(
                    time.perf_counter() - started, 3
                ),
            }
            save_results(results, gold_ids)

            print("STATUS: ERROR")
            print("Reason:", str(exc)[:500])

            # Stop rather than repeatedly calling an unavailable API
            # or exhausting provider limits.
            break

    print("\n" + "=" * 65)
    print("SESSION SUMMARY")
    print("=" * 65)

    completed = sum(
        x.get("status") == "completed"
        for x in results.values()
    )

    print(f"Completed: {completed}/40")
    print(f"Remaining: {40 - completed}")
    print("Raw results:", OUTPUT)
    print("Factual accuracy: NOT YET SCORED")
    print("Citation faithfulness: NOT YET SCORED")


if __name__ == "__main__":
    main()
