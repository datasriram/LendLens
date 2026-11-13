# LendLens corpus quality gates

The raw corpus is an immutable acquisition layer. It is **not** indexed directly.

## Why a curation layer is necessary

A real website crawl can contain duplicate payloads, collection/index pages, navigation fragments, repeated URLs, low-text PDFs, or pages that only exist to discover other documents. Indexing all of these would pollute retrieval and inflate corpus statistics.

## Baseline curation rules

1. **SHA-256 deduplication** — one canonical record is selected per unique content hash. Duplicate files remain in the audit trail but are excluded from indexing.
2. **Collection/index pages are discovery-only** — seed pages and catalogue pages are not part of the semantic knowledge base unless they contain substantive policy content.
3. **HTML quality gate** — pages with very little substantive visible text are excluded; navigation-heavy pages are excluded.
4. **PDF text-extraction gate** — PDFs with insufficient extractable text are flagged for later OCR/layout processing rather than silently indexed as empty text.
5. **Raw originals remain immutable** — curation produces manifests; it does not rewrite or delete authoritative source files.
6. **Downstream ingestion must read `data/manifests/index_manifest.jsonl`**, not crawl `data/raw` directly.

## Outputs

- `data/manifests/curation_manifest.jsonl` — every acquisition record plus the curation decision and reason.
- `data/manifests/index_manifest.jsonl` — only canonical documents approved for downstream parsing/indexing.
- `data/reports/indexable_corpus_inventory.csv` — professor-friendly inventory of approved documents.
- `data/reports/curation_report.json` — aggregate quality statistics and exclusion reasons.

These rules are intentionally a **baseline**. Later retrieval evaluation may justify revising them. The curation process should be version-controlled so the benchmark corpus is reproducible.
