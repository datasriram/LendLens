# LendLens
### Financial Regulatory Intelligence Using Hybrid RAG

LendLens is an evidence-grounded Retrieval-Augmented Generation (RAG) application designed to answer questions about Indian RBI regulations and publicly available NBFC policies.

It combines hybrid retrieval, metadata-aware routing, cross-encoder reranking, context expansion, and LLM generation to produce source-supported regulatory answers.

## Key Features

- Hybrid retrieval combining dense embeddings and BM25 sparse search
- Reciprocal Rank Fusion (RRF) using Qdrant
- Cross-encoder reranking for improved evidence selection
- Metadata-aware routing across RBI regulations and NBFC policies
- Authority-aware and temporal source handling
- Context expansion for retrieving surrounding evidence
- Grounded answer generation with source citations
- Abstention mechanisms for insufficient evidence
- Guardrails for restricted lending decisions
- FastAPI backend and Streamlit frontend
- Support for local Ollama and hosted Groq models

## Architecture

1. User submits a regulatory question through Streamlit.
2. FastAPI receives and validates the request.
3. Query guardrails check for restricted requests.
4. Metadata-aware routing identifies relevant source categories.
5. Dense and sparse retrieval search the Qdrant knowledge base.
6. Reciprocal Rank Fusion combines retrieval results.
7. Cross-encoder reranking improves evidence ranking.
8. Context expansion retrieves additional supporting information.
9. The language model generates an evidence-grounded answer.
10. Citation validation and abstention logic process the response.

## Technology Stack

| Component | Technology |
|---|---|
| Programming | Python |
| Frontend | Streamlit |
| Backend | FastAPI |
| Vector Database | Qdrant |
| Dense Embeddings | BAAI/bge-small-en-v1.5 |
| Sparse Retrieval | BM25 |
| Fusion | Reciprocal Rank Fusion |
| Reranking | Cross-Encoder |
| Generation | Qwen via Ollama or Groq |
| Evaluation | Pytest and custom benchmark scripts |

## Project Structure

- src/ : Core RAG implementation
- api/ : FastAPI backend
- scripts/ : Corpus preparation and evaluation tools
- config/ : Application configuration
- data/ : Corpus manifests and metadata reports
- docs/ : Research and technical documentation
- tests/ : Integration tests
- streamlit_app.py : Interactive frontend
- requirements.txt : Python dependencies

The original source-document corpus and local vector databases are excluded from the public repository.

## Local Setup

Requires Python 3.12 and an indexed LendLens knowledge base.

1. Clone the repository.
2. Create a Python virtual environment.
3. Install dependencies using requirements.txt.
4. Prepare and index the RBI/NBFC corpus using the provided scripts.
5. Configure the generation provider and required credentials.
6. Start the FastAPI backend with start_api.ps1.
7. Start the Streamlit frontend with start_ui.ps1.

The default configuration uses local Qdrant and Ollama with Qwen3 4B.

## Cloud Deployment

LendLens supports configurable hosted generation and vector storage.

Environment variables:

- GROQ_API_KEY
- LENDLENS_GENERATION_PROVIDER
- LENDLENS_QDRANT_URL
- LENDLENS_QDRANT_API_KEY
- LENDLENS_API_URL

Set actual credentials through deployment secrets, never in source code.

Cloud deployment and remote collection migration are pending verification.

## Evaluation Methodology

A 180-question evaluation benchmark was prepared across regulatory lookup, company policy, cross-document reasoning, temporal validity, authority handling, abstention, and adversarial safety.

The evaluation design separates:

- 40 gold-standard validation questions
- 140 held-out final evaluation questions

Evaluation dimensions include Recall@K, MRR, answer correctness, faithfulness, citation accuracy, authority correctness, temporal correctness, and abstention performance.

### Current Results

The Groq/Qwen behavioral benchmark has completed 12 successful cases, with zero observed failures among completed cases.

Eight additional cases remain incomplete due to provider rate limits.

Full factual evaluation and final held-out testing remain pending.

These preliminary results do not establish production reliability or overall factual accuracy.

## Live Demo

Deployment pending.

## Planned Improvements

- Complete gold-standard evaluation
- Complete held-out benchmark testing
- Verify cloud deployment
- Improve latency and retrieval quality
- Strengthen safety and adversarial robustness
- Extend agent-based financial workflows

## Disclaimer

LendLens is an educational and research project. It is not a substitute for official RBI guidance, legal advice, or professional financial advice.
