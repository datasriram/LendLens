# LendLens Corpus Strengthening v1.2

The v1.1 curation report proved that raw volume was sufficient but exposed three quality problems:

1. regulatory evidence was underrepresented relative to company documents;
2. crawler-discovered documents were mostly labelled `discovered` with unknown temporal metadata;
3. one publisher could dominate baseline retrieval merely because its website exposed many crawlable documents.

v1.2 therefore does **not delete the raw corpus**. It adds a regulatory acquisition pass, enriches metadata conservatively, and creates two downstream manifests:

- `enriched_index_manifest.jsonl`: every canonical indexable document, with enriched category/authority/tier metadata;
- `core_index_manifest.jsonl`: a balanced experimental subset for the first retrieval benchmarks.

The core manifest is not the final production corpus. It exists so that dense/hybrid/reranking experiments measure retrieval quality rather than website-crawl volume.

## Important temporal rule

The script never marks a document legally "current" merely because its title contains a recent year. Temporal status is preserved from trusted catalogue metadata when available; otherwise it remains unverified. This is intentional because legal/regulatory applicability must be source-verified.

## Acceptance gates before RAG benchmarking

- at least 150 indexable documents;
- at least 15 official RBI regulatory/interpretive documents;
- no more than 15% unclassified documents after metadata enrichment;
- no single publisher above 35% of the **core experimental** manifest.

These gates can be revised later, but they force the project to make corpus quality measurable rather than subjective.
