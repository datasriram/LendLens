# LendLens knowledge base — professor note

This repository contains the **corpus acquisition layer** for an end-to-end NBFC RAG system. The knowledge base is built from real public sources rather than generated policy documents.

The corpus is intentionally split across two authority classes:

- **Reserve Bank of India material**: master directions, notifications, FAQs and consumer-protection material.
- **Public NBFC material**: fair-practices codes, grievance policies, lending/auction/interest-rate policies, annual reports, financial statements and digital-lending disclosures from major Indian NBFCs.

The source catalogue contains direct verified public sources and collection pages from Bajaj Finance, Shriram Finance, Muthoot Finance, Mahindra Finance, Cholamandalam Finance, Tata Capital/Tata Capital Housing Finance, Manappuram Finance and IIFL Finance. A controlled downloader preserves the original files, final source URL, retrieval timestamp and SHA-256 checksum.

Historical versions are retained on purpose. The project will test whether retrieval can prefer the currently applicable RBI/company policy while still supporting historical questions. This creates a realistic temporal-RAG problem rather than a simple semantic-search demo.

The knowledge-base build is only Phase 1. Later phases add parsing/chunking experiments, Qdrant hybrid retrieval, reranking, local Qwen3 generation through Ollama, evaluation, safety, observability, FastAPI, UI and Docker deployment.
