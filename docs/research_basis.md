# Research basis for the LendLens corpus

This corpus is intentionally heterogeneous. It mixes regulator directions, FAQs, company policies, annual reports, financial statements and customer-facing disclosures because real financial RAG systems fail when the retrieval problem is reduced to a single clean PDF.

## External work reviewed

- **FinDoc-RAG (FinNLP 2025)** — real-world financial documents and retrieval-augmented QA; useful evidence that cross-document synthesis remains materially harder than direct factual lookup. https://aclanthology.org/2025.finnlp-2.9/
- **FinanceBench** — financial QA benchmark grounded in company filings with evidence annotations. https://github.com/cyzc-ai/financebench and https://rag-repo.org/source/financebench/
- **FinMRAGBench (ACL Findings 2026)** — multi-document / multi-page financial RAG benchmark. https://aclanthology.org/2026.findings-acl.187/
- **T2-RAGBench** — text + table financial reasoning benchmark over thousands of reports. https://t2ragbench.demo.hcds.uni-hamburg.de/
- **Open-source FinanceBench RAG implementations** — useful for studying page-level retrieval, metadata filters, hybrid search and failure analysis. Example: https://github.com/aquib8112/FinanceBench_RAG
- **Structure-aware financial RAG projects** — motivate evaluating layout/section-aware retrieval rather than assuming fixed recursive chunks are optimal. Example: https://github.com/AsyncBuilds/FinRag

## Design implication

The current project baseline (recursive chunks + BGE dense embeddings + BM25 sparse retrieval + Qdrant hybrid search + optional cross-encoder reranking) is retained as **Baseline V1**. Later phases compare that baseline against stronger parsing/chunking strategies using measured retrieval metrics rather than replacing components by intuition.
