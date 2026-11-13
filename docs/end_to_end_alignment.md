# End-to-end alignment

The knowledge base is only one subsystem. The final project scope remains:

1. **Corpus engineering** — authoritative acquisition, provenance, version status, checksums, duplicates, raw immutable source store.
2. **Parsing and chunking** — baseline recursive/page-aware strategy, then table/section-aware experiments.
3. **Indexing** — local BGE dense embeddings + BM25 sparse vectors in Qdrant.
4. **Retrieval** — dense, hybrid, metadata/temporal filtering, optional cross-encoder reranking.
5. **Generation** — local Qwen3 via Ollama, grounded answers, page/source citations and abstention.
6. **Evaluation** — Recall@K, MRR/nDCG, answer correctness, numeric accuracy, citation correctness, faithfulness, abstention, version-currentness and source-authority correctness.
7. **Safety** — allowlisted sources, provenance checks, prompt-injection tests, retrieved-text-as-data boundary, PII policy, no automated credit approval.
8. **Observability** — OpenTelemetry-style traces / Arize Phoenix candidate, stage latency, retrieved documents, reranker scores, citation mapping and failure analysis.
9. **Serving** — FastAPI with typed schemas and health/query/document endpoints.
10. **Demo** — Streamlit UI for cited NBFC regulatory/policy research.
11. **Packaging** — Docker, configuration, tests, deployment notes, reproducibility.

The project is positioned as **decision-support / regulatory intelligence**, not autonomous underwriting or financial advice.
