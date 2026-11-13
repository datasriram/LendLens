from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
import pymupdf

CATEGORY_PATTERNS = [
    ("kyc_aml", r"\bkyc\b|know your customer|anti[- ]money laundering|\baml\b|customer due diligence|\bcdd\b"),
    ("digital_lending", r"digital lending|lending service provider|\blsp\b|digital lending app|\bdla\b|default loss guarantee|\bdlg\b"),
    ("fair_practices", r"fair practice|fair practices|fair lending|penal charge|customer conduct"),
    ("grievance", r"grievance|ombudsman|complaint|redressal|customer service"),
    ("fraud_risk", r"fraud risk|fraud management|fraud prevention|early warning signal"),
    ("it_cyber", r"cyber|information technology|it governance|information security|operational resilience|business continuity"),
    ("it_outsourcing", r"outsourcing.*information technology|it outsourcing|technology service provider"),
    ("microfinance", r"microfinance|nbfc[- ]mfi|qualifying assets"),
    ("collections_recovery", r"collection|recovery|repossession|auction|sarfaesi"),
    ("interest_rate", r"interest rate policy|pricing policy|annual percentage rate|\bapr\b|rate of interest"),
    ("loan_policy", r"loan policy|credit policy|lending policy|credit underwriting"),
    ("responsible_lending", r"responsible lending|property documents|floating interest|pre[- ]payment|foreclosure"),
    ("wilful_default", r"wilful defaulter|willful defaulter|large defaulter"),
    ("stressed_assets", r"stressed asset|compromise settlement|technical write[- ]off|restructuring|resolution framework|\bnpa\b"),
    ("co_lending", r"co[- ]lending|co lending"),
    ("gold_loans", r"gold loan|gold and silver collateral|pledge of gold|gold collateral"),
    ("public_deposits", r"public deposit|acceptance of deposits"),
    ("financial_statements", r"financial statement|balance sheet|profit and loss|statement of profit|standalone financial|consolidated financial"),
    ("annual_report", r"annual report|management discussion|directors'? report|business responsibility"),
    ("governance", r"corporate governance|board policy|risk management committee|chief compliance officer"),
    ("privacy", r"privacy policy|data protection|personal data"),
    ("terms", r"terms and conditions|terms of use"),
]

POLICY_CATEGORIES = {
    "kyc_aml", "digital_lending", "fair_practices", "grievance", "collections_recovery",
    "interest_rate", "loan_policy", "governance", "privacy", "terms", "responsible_lending",
}
REGULATORY_CATEGORIES = {
    "kyc_aml", "digital_lending", "fair_practices", "grievance", "fraud_risk", "it_cyber",
    "it_outsourcing", "microfinance", "responsible_lending", "wilful_default", "stressed_assets",
    "co_lending", "gold_loans", "public_deposits", "nbfc_regulation", "fair_lending",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def sample_text(root: Path, row: dict[str, Any], limit: int = 12000) -> str:
    path = root / str(row.get("local_path", ""))
    if not path.exists():
        return ""
    try:
        if path.suffix.lower() == ".pdf":
            doc = pymupdf.open(path)
            parts = []
            for page in list(doc)[:3]:
                parts.append(page.get_text("text"))
                if sum(len(x) for x in parts) >= limit:
                    break
            doc.close()
            return " ".join(parts)[:limit]
        if path.suffix.lower() in {".html", ".htm"}:
            soup = BeautifulSoup(path.read_bytes(), "html.parser")
            for tag in soup(["script", "style", "noscript", "svg", "canvas", "form", "nav", "header", "footer", "aside"]):
                tag.decompose()
            return " ".join(soup.stripped_strings)[:limit]
    except Exception:
        return ""
    return ""


def infer_category(blob: str, original: str) -> tuple[str, float]:
    # Respect curated, meaningful categories. Only reclassify generic/discovered buckets.
    if original and original not in {"discovered", "unknown", "other", ""}:
        return original, 1.0
    text = blob.lower()
    for category, pattern in CATEGORY_PATTERNS:
        if re.search(pattern, text, flags=re.I):
            return category, 0.85
    return "unclassified_public_source", 0.0


def infer_year(blob: str) -> int | None:
    years = [int(x) for x in re.findall(r"\b(20(?:1\d|2\d))\b", blob)]
    return max(years) if years else None


def infer_authority(row: dict[str, Any], category: str) -> str:
    publisher = str(row.get("publisher_canonical") or row.get("publisher") or "")
    existing = str(row.get("authority") or "")
    if publisher == "Reserve Bank of India" or existing == "regulator":
        return "regulator"
    if category in POLICY_CATEGORIES:
        return "company_policy"
    if category in {"annual_report", "financial_statements"}:
        return "company_public_disclosure"
    return existing or "company_public_source"


def corpus_tier(authority: str, category: str) -> str:
    if authority == "regulator":
        return "core_regulatory"
    if authority == "company_policy":
        return "core_company_policy"
    if category in {"annual_report", "financial_statements"} or authority in {"company_public_disclosure", "company_disclosure"}:
        return "supporting_corporate_disclosure"
    return "secondary_public_source"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=".")
    p.add_argument("--input", default="data/manifests/index_manifest.jsonl")
    args = p.parse_args()
    root = Path(args.root).resolve()
    rows = read_jsonl(root / args.input)

    enriched = []
    for row in rows:
        r = dict(row)
        blob = " ".join([
            str(r.get("title", "")), str(r.get("final_url", "")), str(r.get("requested_url", "")),
            str(r.get("notes", "")), sample_text(root, r)
        ])
        category, confidence = infer_category(blob, str(r.get("category", "")))
        authority = infer_authority(r, category)
        year = infer_year(" ".join([str(r.get("title", "")), str(r.get("local_path", "")), str(r.get("notes", ""))]))
        r["category_original"] = r.get("category", "")
        r["category_enriched"] = category
        r["category_confidence"] = confidence
        r["authority_enriched"] = authority
        r["document_year_inferred"] = year
        r["corpus_tier"] = corpus_tier(authority, category)
        # Never invent legal/current status when the source did not provide it.
        if not r.get("temporal_role"):
            r["temporal_role"] = "unknown"
        r["temporal_status_verified"] = str(r.get("temporal_role")) not in {"unknown", "", "discovery_only"}
        enriched.append(r)

    out = root / "data/manifests/enriched_index_manifest.jsonl"
    write_jsonl(out, enriched)

    # Build a deterministic core manifest for retrieval experiments. The full enriched manifest is retained.
    core = []
    by_publisher_secondary: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in enriched:
        if r["corpus_tier"] in {"core_regulatory", "core_company_policy"}:
            core.append(r)
        else:
            by_publisher_secondary[str(r.get("publisher_canonical") or r.get("publisher") or "unknown")].append(r)
    for publisher, group in sorted(by_publisher_secondary.items()):
        # Keep enough corporate evidence for realism, but prevent one crawler-rich publisher from dominating baseline retrieval.
        selected = sorted(group, key=lambda x: (x["corpus_tier"] != "supporting_corporate_disclosure", str(x.get("source_id", ""))))[:20]
        core.extend(selected)
    core = sorted(core, key=lambda x: (str(x.get("publisher_canonical") or x.get("publisher") or ""), str(x.get("source_id", ""))))
    write_jsonl(root / "data/manifests/core_index_manifest.jsonl", core)

    def summarize(data: list[dict[str, Any]]) -> dict[str, Any]:
        pubs = Counter(str(r.get("publisher_canonical") or r.get("publisher") or "unknown") for r in data)
        cats = Counter(str(r.get("category_enriched") or "unknown") for r in data)
        auth = Counter(str(r.get("authority_enriched") or "unknown") for r in data)
        tiers = Counter(str(r.get("corpus_tier") or "unknown") for r in data)
        unresolved_cat = sum(1 for r in data if r.get("category_enriched") == "unclassified_public_source")
        unresolved_time = sum(1 for r in data if not r.get("temporal_status_verified"))
        max_pub = max(pubs.values()) if pubs else 0
        return {
            "documents": len(data),
            "publishers": dict(sorted(pubs.items())),
            "categories": dict(sorted(cats.items())),
            "authority": dict(sorted(auth.items())),
            "tiers": dict(sorted(tiers.items())),
            "unresolved_category_documents": unresolved_cat,
            "unresolved_category_rate": round(unresolved_cat / len(data), 4) if data else 0,
            "unverified_temporal_documents": unresolved_time,
            "unverified_temporal_rate": round(unresolved_time / len(data), 4) if data else 0,
            "largest_publisher_documents": max_pub,
            "largest_publisher_share": round(max_pub / len(data), 4) if data else 0,
            "regulator_documents": auth.get("regulator", 0),
        }

    report = {
        "full_enriched_index": summarize(enriched),
        "core_experimental_index": summarize(core),
        "acceptance_gates": {
            "min_full_documents": 150,
            "min_regulator_documents": 15,
            "max_core_largest_publisher_share": 0.35,
            "max_full_unresolved_category_rate": 0.15,
            "note": "Temporal status is not inferred as legally current from year alone; unknowns remain explicit until verified.",
        },
    }
    s = report["full_enriched_index"]
    c = report["core_experimental_index"]
    report["gate_results"] = {
        "full_document_volume": s["documents"] >= 150,
        "regulatory_coverage": s["regulator_documents"] >= 15,
        "metadata_category_resolution": s["unresolved_category_rate"] <= 0.15,
        "core_publisher_balance": c["largest_publisher_share"] <= 0.35,
    }
    report["overall_ready_for_retrieval_baseline"] = all(report["gate_results"].values())

    reports = root / "data/reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "metadata_coverage_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    fields = [
        "source_id", "publisher", "publisher_canonical", "title", "category_original", "category_enriched",
        "category_confidence", "authority_enriched", "temporal_role", "temporal_status_verified",
        "document_year_inferred", "corpus_tier", "source_kind", "pdf_pages", "word_count", "local_path", "final_url", "sha256",
    ]
    with (reports / "enriched_corpus_inventory.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in enriched:
            w.writerow(r)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("Enriched manifest:", out)
    print("Core manifest:", root / "data/manifests/core_index_manifest.jsonl")


if __name__ == "__main__":
    main()
