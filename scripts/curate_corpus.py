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

GENERIC_TITLES = {
    "skip to main content",
    "others",
    "reach us",
    "home",
    "contact us",
    "about us",
    "annual reports",
    "policies",
    "investor relations",
    "downloads",
    "sitemap",
}

DISCOVERY_ONLY_CATEGORIES = {
    "collection_page",
    "annual_reports",
    "policies",
}

AUTHORITY_RANK = {
    "regulator": 5,
    "company_policy": 4,
    "company_public_disclosure": 3,
    "company_disclosure": 3,
    "company_public_source": 2,
    "reference": 1,
    "": 0,
}


PUBLISHER_CANONICAL = {
    "Mahindra Finance": "Mahindra & Mahindra Financial Services Limited",
    "Cholamandalam Finance": "Cholamandalam Investment and Finance Company Limited",
}

ACQUISITION_RANK = {
    "curated_direct": 4,
    "discovered_from_official_collection": 3,
    "collection_seed": 1,
    "": 0,
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at line {i}: {exc}") from exc
    return out


def visible_html_text(path: Path) -> tuple[str, int, int]:
    data = path.read_bytes()
    soup = BeautifulSoup(data, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "canvas", "form"]):
        tag.decompose()
    # Remove common chrome so quality statistics focus on substantive content.
    for selector in ["nav", "header", "footer", "aside"]:
        for tag in soup.find_all(selector):
            tag.decompose()
    text = " ".join(soup.stripped_strings)
    words = re.findall(r"\b\w+\b", text, flags=re.UNICODE)
    links = soup.find_all("a", href=True)
    return text, len(words), len(links)


def pdf_stats(path: Path) -> tuple[int, int]:
    pages = 0
    words = 0
    with pymupdf.open(path) as doc:
        pages = len(doc)
        # Full-corpus text extraction is intentionally limited to word counting.
        # This is still useful for spotting scans/blank PDFs before indexing.
        for page in doc:
            words += len(page.get_text("words"))
    return pages, words


def title_is_generic(title: str) -> bool:
    norm = re.sub(r"\s+", " ", (title or "").strip().lower())
    return norm in GENERIC_TITLES or norm.startswith("skip to ")


def candidate_score(record: dict[str, Any]) -> tuple[int, int, int, int, int]:
    acquisition = ACQUISITION_RANK.get(str(record.get("acquisition_mode", "")), 0)
    authority = AUTHORITY_RANK.get(str(record.get("authority", "")), 0)
    kind = 2 if record.get("source_kind") == "pdf" else 1
    direct = 1 if str(record.get("source_id", "")).startswith("rbi_") or record.get("acquisition_mode") == "curated_direct" else 0
    meaningful_title = 0 if title_is_generic(str(record.get("title", ""))) else 1
    return acquisition, authority, kind, direct, meaningful_title


def decide_indexability(record: dict[str, Any], root: Path) -> tuple[bool, str, dict[str, Any]]:
    path_text = str(record.get("local_path", ""))
    if not path_text:
        return False, "missing_local_path", {}
    path = root / path_text
    if not path.exists() or not path.is_file():
        return False, "missing_file", {}
    if path.name == ".gitkeep":
        return False, "placeholder_file", {}

    acquisition = str(record.get("acquisition_mode", ""))
    category = str(record.get("category", ""))
    temporal_role = str(record.get("temporal_role", ""))
    title = str(record.get("title", ""))
    source_kind = str(record.get("source_kind", "")).lower()

    if acquisition == "collection_seed":
        return False, "discovery_collection_page", {}
    if category in DISCOVERY_ONLY_CATEGORIES or temporal_role == "collection":
        return False, "collection_or_index_page", {}
    if title_is_generic(title):
        return False, "generic_navigation_page", {}

    stats: dict[str, Any] = {"bytes_on_disk": path.stat().st_size}

    try:
        if source_kind == "pdf" or path.suffix.lower() == ".pdf":
            pages, words = pdf_stats(path)
            stats.update({"pdf_pages": pages, "word_count": words})
            if pages <= 0:
                return False, "empty_pdf", stats
            # Very low extracted text usually means a scan or non-text PDF. Keep it out
            # of the baseline text RAG and flag it for future OCR/layout processing.
            if words < max(25, pages * 8):
                return False, "pdf_low_extractable_text_needs_ocr_review", stats
            return True, "index", stats

        if source_kind == "html" or path.suffix.lower() in {".html", ".htm"}:
            _, words, links = visible_html_text(path)
            stats.update({"word_count": words, "link_count": links})
            if words < 120:
                return False, "html_low_substantive_text", stats
            # A page with a very large number of links and little prose is usually an index.
            if links >= 40 and words < 600:
                return False, "html_navigation_heavy", stats
            return True, "index", stats
    except Exception as exc:
        stats["quality_error"] = repr(exc)
        return False, "parse_or_quality_check_failed", stats

    return False, "unsupported_file_type", stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Curate the raw LendLens corpus into an indexable manifest without mutating raw originals.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--manifest", default="data/manifests/download_manifest.jsonl")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    manifest_path = root / args.manifest
    records = read_jsonl(manifest_path)

    # Keep only records that actually produced a local file.
    local_records = [r for r in records if r.get("local_path") and str(r.get("status")) in {"downloaded", "duplicate_content"}]
    failures = [r for r in records if str(r.get("status")) not in {"downloaded", "duplicate_content"}]

    by_sha: dict[str, list[dict[str, Any]]] = defaultdict(list)
    no_sha: list[dict[str, Any]] = []
    for r in local_records:
        sha = str(r.get("sha256", ""))
        if sha:
            by_sha[sha].append(r)
        else:
            no_sha.append(r)

    canonical_by_sha: dict[str, dict[str, Any]] = {}
    for sha, group in by_sha.items():
        canonical_by_sha[sha] = max(group, key=candidate_score)

    decisions: list[dict[str, Any]] = []
    duplicate_aliases = 0

    for sha, group in by_sha.items():
        canonical = canonical_by_sha[sha]
        canonical_id = str(canonical.get("source_id", ""))
        for r in group:
            is_canonical = r is canonical
            row = dict(r)
            row["publisher_canonical"] = PUBLISHER_CANONICAL.get(str(r.get("publisher", "")), str(r.get("publisher", "")))
            row["canonical_source_id"] = canonical_id
            row["is_canonical"] = is_canonical
            if not is_canonical:
                duplicate_aliases += 1
                row["indexable"] = False
                row["curation_reason"] = "duplicate_sha256_alias"
                decisions.append(row)
                continue
            indexable, reason, stats = decide_indexability(r, root)
            row.update(stats)
            row["indexable"] = indexable
            row["curation_reason"] = reason
            decisions.append(row)

    for r in no_sha:
        row = dict(r)
        row["publisher_canonical"] = PUBLISHER_CANONICAL.get(str(r.get("publisher", "")), str(r.get("publisher", "")))
        row["canonical_source_id"] = str(r.get("source_id", ""))
        row["is_canonical"] = True
        indexable, reason, stats = decide_indexability(r, root)
        row.update(stats)
        row["indexable"] = indexable
        row["curation_reason"] = reason
        decisions.append(row)

    # Preserve failed acquisition records in the full curation manifest for auditability.
    for r in failures:
        row = dict(r)
        row["publisher_canonical"] = PUBLISHER_CANONICAL.get(str(r.get("publisher", "")), str(r.get("publisher", "")))
        row["canonical_source_id"] = ""
        row["is_canonical"] = False
        row["indexable"] = False
        row["curation_reason"] = "acquisition_failed"
        decisions.append(row)

    indexable = [r for r in decisions if r.get("indexable") is True]
    excluded = [r for r in decisions if r.get("indexable") is not True]

    manifests_dir = root / "data" / "manifests"
    reports_dir = root / "data" / "reports"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    full_manifest = manifests_dir / "curation_manifest.jsonl"
    index_manifest = manifests_dir / "index_manifest.jsonl"
    with full_manifest.open("w", encoding="utf-8") as f:
        for row in decisions:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with index_manifest.open("w", encoding="utf-8") as f:
        for row in indexable:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    inventory_path = reports_dir / "indexable_corpus_inventory.csv"
    inventory_fields = [
        "source_id", "publisher", "publisher_canonical", "entity", "category", "title", "source_kind",
        "authority", "temporal_role", "acquisition_mode", "local_path", "final_url",
        "sha256", "bytes_on_disk", "pdf_pages", "word_count", "curation_reason",
    ]
    with inventory_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=inventory_fields, extrasaction="ignore")
        writer.writeheader()
        for row in sorted(indexable, key=lambda x: (str(x.get("publisher", "")), str(x.get("category", "")), str(x.get("title", "")))):
            writer.writerow(row)

    publisher_counts = Counter(str(r.get("publisher_canonical", r.get("publisher", "unknown"))) for r in indexable)
    category_counts = Counter(str(r.get("category", "unknown")) for r in indexable)
    kind_counts = Counter(str(r.get("source_kind", "unknown")) for r in indexable)
    authority_counts = Counter(str(r.get("authority", "unknown")) for r in indexable)
    temporal_counts = Counter(str(r.get("temporal_role", "unknown")) for r in indexable)
    exclusion_counts = Counter(str(r.get("curation_reason", "unknown")) for r in excluded)

    report = {
        "raw_manifest_records": len(records),
        "downloaded_file_records": len(local_records),
        "acquisition_failures": len(failures),
        "unique_content_hashes": len(by_sha) + len(no_sha),
        "duplicate_alias_records": duplicate_aliases,
        "indexable_documents": len(indexable),
        "excluded_records": len(excluded),
        "indexable_pdf_documents": sum(1 for r in indexable if r.get("source_kind") == "pdf"),
        "indexable_html_documents": sum(1 for r in indexable if r.get("source_kind") == "html"),
        "indexable_pdf_pages": sum(int(r.get("pdf_pages", 0) or 0) for r in indexable),
        "indexable_bytes": sum(int(r.get("bytes_on_disk", 0) or 0) for r in indexable),
        "indexable_words_estimate": sum(int(r.get("word_count", 0) or 0) for r in indexable),
        "publishers": dict(sorted(publisher_counts.items())),
        "categories": dict(sorted(category_counts.items())),
        "source_kinds": dict(sorted(kind_counts.items())),
        "authority_levels": dict(sorted(authority_counts.items())),
        "temporal_roles": dict(sorted(temporal_counts.items())),
        "exclusions": dict(sorted(exclusion_counts.items())),
        "quality_gate": {
            "principle": "Raw originals are immutable; only index_manifest.jsonl feeds downstream parsing/indexing.",
            "html_min_words": 120,
            "navigation_heavy_rule": "exclude if >=40 links and <600 visible words",
            "pdf_low_text_rule": "exclude from baseline text RAG when extracted words < max(25, pages*8); review later for OCR/layout parsing",
            "duplicate_rule": "one canonical record per SHA-256; aliases remain in audit manifest but are not indexed",
        },
    }
    report_path = reports_dir / "curation_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nFull audit manifest: {full_manifest}")
    print(f"Indexable manifest:  {index_manifest}")
    print(f"Inventory CSV:       {inventory_path}")
    print(f"Curation report:     {report_path}")


if __name__ == "__main__":
    main()
