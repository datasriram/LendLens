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

# Ordered from specific to broad.
CATEGORY_PATTERNS = [
    ("internal_ombudsman", r"internal ombudsman"),
    ("kyc_aml", r"\bkyc\b|know your customer|anti[- ]money laundering|\baml\b|customer due diligence|\bcdd\b|ckyc"),
    ("digital_lending", r"digital lending|lending service provider|\blsp\b|digital lending app|\bdla\b|default loss guarantee|\bdlg\b"),
    ("responsible_business_conduct", r"responsible business conduct|key facts statement|penal charges|fair lending"),
    ("fair_practices", r"fair practice|fair practices code|fair lending|customer conduct"),
    ("grievance", r"grievance|ombudsman|complaint|redressal|customer service"),
    ("fraud_risk", r"fraud risk|fraud management|fraud prevention|early warning signal"),
    ("cybersecurity", r"cybersecurity|cyber security|information security|operational resilience|security controls"),
    ("it_outsourcing", r"outsourcing.*information technology|it outsourcing|technology service provider"),
    ("outsourcing", r"managing risks in outsourcing|outsourcing of financial services"),
    ("microfinance", r"microfinance|nbfc[- ]mfi|qualifying assets"),
    ("collections_recovery", r"collection|recovery|repossession|auction|sarfaesi"),
    ("interest_rate", r"interest rate policy|pricing policy|annual percentage rate|\bapr\b|rate of interest"),
    ("loan_policy", r"loan policy|credit policy|lending policy|credit underwriting"),
    ("responsible_lending", r"responsible lending|property documents|floating interest|pre[- ]payment|foreclosure"),
    ("wilful_default", r"wilful defaulter|willful defaulter|large defaulter"),
    ("stressed_assets", r"stressed asset|compromise settlement|technical write[- ]off|restructuring|resolution framework|\bnpa\b"),
    ("asset_classification", r"income recognition|asset classification|provisioning norms"),
    ("asset_liability_management", r"asset liability management|\balm\b"),
    ("credit_risk", r"credit risk management|credit risk evaluation"),
    ("credit_information", r"credit information reporting|credit information compan"),
    ("credit_facilities", r"credit facilities|credit products"),
    ("co_lending", r"co[- ]lending|co lending"),
    ("gold_loans", r"gold loan|gold and silver collateral|pledge of gold|gold collateral|auction of gold"),
    ("public_deposits", r"public deposit|acceptance of deposits"),
    ("capital_adequacy", r"capital adequacy|capital requirement"),
    ("financial_statements", r"financial statement|balance sheet|profit and loss|statement of profit|standalone financial|consolidated financial"),
    ("annual_report", r"annual report|management discussion|directors'? report|business responsibility"),
    ("governance", r"corporate governance|board policy|risk management committee|chief compliance officer|fit and proper"),
    ("risk_management", r"risk management policy|enterprise risk|risk management framework"),
    ("audit_compliance", r"statutory audit|internal audit|audit committee|compliance function|compliance policy"),
    ("whistleblower", r"whistle.?blower|vigil mechanism"),
    ("related_party", r"related party|arm.?s length"),
    ("remuneration", r"remuneration policy|nomination and remuneration|compensation policy"),
    ("csr_esg", r"corporate social responsibility|\bcsr\b|environment social governance|\besg\b|sustainability"),
    ("code_of_conduct", r"code of conduct|code of ethics"),
    ("privacy", r"privacy policy|data protection|personal data"),
    ("terms", r"terms and conditions|terms of use"),
    ("customer_disclosures", r"customer disclosure|customer charter|citizen.?s charter|service charges|fees and charges"),
    ("investor_disclosure", r"investor relation|investor presentation|shareholder|stock exchange disclosure|corporate announcement"),
    ("policy_inventory", r"policies codes and other documents|policy inventory|corporate policies"),
    ("product_information", r"personal loan|business loan|vehicle finance|home loan|gold loan|loan against property|product note"),
]

POLICY_CATEGORIES = {
    "kyc_aml", "digital_lending", "responsible_business_conduct", "fair_practices", "grievance",
    "collections_recovery", "interest_rate", "loan_policy", "governance", "risk_management",
    "audit_compliance", "whistleblower", "related_party", "remuneration", "code_of_conduct",
    "privacy", "terms", "customer_disclosures", "policy_inventory", "responsible_lending",
}

CORE_CATEGORY_PRIORITY = {
    "kyc_aml": 0, "digital_lending": 1, "responsible_business_conduct": 2, "fair_practices": 3,
    "grievance": 4, "collections_recovery": 5, "loan_policy": 6, "interest_rate": 7,
    "responsible_lending": 8, "fraud_risk": 9, "cybersecurity": 10, "it_outsourcing": 11,
    "outsourcing": 12, "stressed_assets": 13, "credit_risk": 14, "credit_information": 15,
    "gold_loans": 16, "microfinance": 17, "public_deposits": 18, "governance": 19,
    "annual_report": 30, "financial_statements": 31, "investor_disclosure": 32,
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def sample_text(root: Path, row: dict[str, Any], limit: int = 16000) -> str:
    path = root / str(row.get("local_path", ""))
    if not path.exists():
        return ""
    try:
        if path.suffix.lower() == ".pdf":
            doc = pymupdf.open(path)
            parts = []
            for page in list(doc)[:4]:
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


def infer_category(blob: str, original: str) -> tuple[str, float, str]:
    if original and original not in {"discovered", "unknown", "other", "", "unclassified_public_source"}:
        return original, 1.0, "curated_source_metadata"
    text = blob.lower()
    for category, pattern in CATEGORY_PATTERNS:
        if re.search(pattern, text, flags=re.I):
            return category, 0.85, "deterministic_text_rule"
    return "unclassified_public_source", 0.0, "needs_manual_review"


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
    if category in {"annual_report", "financial_statements", "investor_disclosure"}:
        return "company_public_disclosure"
    return existing or "company_public_source"


def corpus_tier(authority: str, category: str) -> str:
    if authority == "regulator":
        return "core_regulatory"
    if authority == "company_policy":
        return "core_company_policy"
    if category in {"annual_report", "financial_statements", "investor_disclosure"} or authority in {"company_public_disclosure", "company_disclosure"}:
        return "supporting_corporate_disclosure"
    return "secondary_public_source"


def core_sort_key(r: dict[str, Any]) -> tuple:
    cat = str(r.get("category_enriched") or "")
    tier = str(r.get("corpus_tier") or "")
    return (
        0 if tier == "core_company_policy" else 1 if tier == "supporting_corporate_disclosure" else 2,
        CORE_CATEGORY_PRIORITY.get(cat, 50),
        str(r.get("source_id", "")),
    )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=".")
    p.add_argument("--input", default="data/manifests/index_manifest.jsonl")
    p.add_argument("--company-cap", type=int, default=18)
    args = p.parse_args()

    root = Path(args.root).resolve()
    rows = read_jsonl(root / args.input)

    enriched = []
    manual_review = []
    for row in rows:
        r = dict(row)
        blob = " ".join([
            str(r.get("title", "")), str(r.get("final_url", "")), str(r.get("requested_url", "")),
            str(r.get("notes", "")), str(r.get("local_path", "")), sample_text(root, r)
        ])
        category, confidence, method = infer_category(blob, str(r.get("category", "")))
        authority = infer_authority(r, category)
        year = infer_year(" ".join([str(r.get("title", "")), str(r.get("local_path", "")), str(r.get("notes", ""))]))
        r["category_original"] = r.get("category", "")
        r["category_enriched"] = category
        r["category_confidence"] = confidence
        r["category_assignment_method"] = method
        r["authority_enriched"] = authority
        r["document_year_inferred"] = year
        r["corpus_tier"] = corpus_tier(authority, category)
        if not r.get("temporal_role"):
            r["temporal_role"] = "unknown"
        r["temporal_status_verified"] = str(r.get("temporal_role")) not in {"unknown", "", "discovery_only"}
        enriched.append(r)
        if category == "unclassified_public_source":
            manual_review.append(r)

    enriched = sorted(enriched, key=lambda x: (str(x.get("publisher_canonical") or x.get("publisher") or ""), str(x.get("source_id", ""))))
    write_jsonl(root / "data/manifests/enriched_index_manifest.jsonl", enriched)

    # All regulator material is preserved in the core. Company material is capped per publisher,
    # prioritising operational/customer-policy content over general corporate pages.
    regulator_rows = [r for r in enriched if r.get("authority_enriched") == "regulator"]
    company_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in enriched:
        if r.get("authority_enriched") == "regulator":
            continue
        pub = str(r.get("publisher_canonical") or r.get("publisher") or "unknown")
        company_groups[pub].append(r)

    core = list(regulator_rows)
    for pub, group in sorted(company_groups.items()):
        core.extend(sorted(group, key=core_sort_key)[: args.company_cap])
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

    full_summary = summarize(enriched)
    core_summary = summarize(core)
    report = {
        "full_enriched_index": full_summary,
        "core_experimental_index": core_summary,
        "acceptance_gates": {
            "min_full_documents": 150,
            "min_regulator_documents": 15,
            "max_core_largest_publisher_share": 0.35,
            "max_full_unresolved_category_rate": 0.15,
            "note": "Temporal status is never inferred as legally current from year alone. Current RBI directions are verified through the RBI Master Directions index; unresolved company temporal status remains explicit.",
        },
        "core_policy": {
            "all_regulator_documents_included": True,
            "max_company_documents_per_publisher": args.company_cap,
            "selection_basis": "deterministic tier + domain category priority; full enriched corpus remains unchanged",
        },
    }
    report["gate_results"] = {
        "full_document_volume": full_summary["documents"] >= 150,
        "regulatory_coverage": full_summary["regulator_documents"] >= 15,
        "metadata_category_resolution": full_summary["unresolved_category_rate"] <= 0.15,
        "core_publisher_balance": core_summary["largest_publisher_share"] <= 0.35,
    }
    report["overall_ready_for_retrieval_baseline"] = all(report["gate_results"].values())

    reports = root / "data/reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "metadata_coverage_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    fields = [
        "source_id", "publisher", "publisher_canonical", "title", "category_original", "category_enriched",
        "category_confidence", "category_assignment_method", "authority_enriched", "temporal_role",
        "temporal_status_verified", "document_year_inferred", "corpus_tier", "source_kind", "pdf_pages",
        "word_count", "local_path", "final_url", "sha256",
    ]
    with (reports / "enriched_corpus_inventory.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in enriched:
            w.writerow(r)

    with (reports / "manual_metadata_review_queue.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in manual_review:
            w.writerow(r)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("Manual metadata review queue:", reports / "manual_metadata_review_queue.csv")


if __name__ == "__main__":
    main()
