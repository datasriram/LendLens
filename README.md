# LendLens

**Evidence-grounded regulatory intelligence for India's NBFC ecosystem.**

LendLens is a Retrieval-Augmented Generation (RAG) application designed to answer questions about Reserve Bank of India (RBI) regulations, NBFC compliance requirements, and publicly available financial-company policies.

Instead of relying solely on model knowledge, the system retrieves regulatory evidence, reranks relevant passages, generates grounded answers, and attaches source references. It also supports abstention and safety guardrails when a question is unsupported or outside its permitted scope.

> **Project status:** Functional research prototype with a completed 40-question validation run. Not intended to replace professional legal or regulatory advice.

## Problem

Indian NBFC regulatory information is distributed across RBI directions, circulars, and company-specific policy disclosures.

Users often need to:

- Find the applicable RBI requirements.
- Understand obligations and limitations.
- Identify authoritative source documents.
- Compare company disclosures with regulatory requirements.
- Distinguish current information from historical material.

Standard document search can retrieve relevant text without synthesizing it. General-purpose language models may produce plausible but unsupported answers.

LendLens combines document retrieval with evidence-constrained generation to address these challenges.

## Architecture

```text
                     User Question
                           |
                           v
                  FastAPI / Streamlit
                           |
                           v
                  Safety Guardrails
                           |
                           v
                   Query Routing
             (authority / topic / time)
                           |
                           v
                  Hybrid Retrieval
                  /              \
            Dense Search      Sparse BM25
                  \              /
                   Reciprocal Rank
                       Fusion
                           |
                           v
                   Cross-Encoder
                      Reranking
                           |
                           v
                  Context Expansion
                           |
                           v
                  Grounded Generation
                    (Groq / Ollama)
                           |
                           v
               Answer + Source References
```

## Technology Stack

| Component | Technology |
|---|---|
| Programming language | Python |
| API framework | FastAPI |
| User interface | Streamlit |
| Vector database | Qdrant (local or cloud) |
| Dense embeddings | BAAI/bge-small-en-v1.5 |
| Sparse retrieval | Qdrant/bm25 |
| Fusion | Reciprocal Rank Fusion (RRF) |
| Reranking | Xenova/ms-marco-MiniLM-L-6-v2 |
| Generation | Groq-hosted Qwen or local Ollama |
| Evaluation | Verified regulatory benchmark, API tests |

## Knowledge Base

The indexed knowledge base contains approximately **15,095 document chunks**.

It covers:

- RBI directions applicable to NBFCs.
- KYC and customer due diligence.
- Digital lending and lending service providers.
- Outsourcing risk management.
- Fraud risk management.
- Cybersecurity and business continuity.
- Stressed assets and asset classification.
- Internal Ombudsman and grievance redressal.
- Selected NBFC public policies and disclosures.

Document metadata includes publisher, regulatory authority, topic category, and temporal status where available.

## How Retrieval Works

### 1. Metadata-Aware Query Routing

Rule-based routing identifies regulatory topics and can apply relevant metadata filters to search for suitable documents.

### 2. Hybrid Search

The system combines dense semantic embeddings and sparse BM25 retrieval through Qdrant.

Reciprocal Rank Fusion merges both retrieval branches.

### 3. Reranking

A cross-encoder reranks the candidate passages for relevance to the original question.

### 4. Context Expansion

Adjacent passages may be included when relevant to improve the evidence available for generation.

### 5. Grounded Generation

The generation layer produces an answer using retrieved evidence and provides source references.

The system can abstain when evidence is insufficient. Guardrails restrict unsupported individual lending decisions and other out-of-scope actions.

## Evaluation

LendLens was evaluated using a verified benchmark containing **180 questions**, divided into:

- **40 validation questions** for development-stage assessment.
- **140 held-out questions** reserved for future final testing.

### Gold-40 Validation Run

| Metric | Result |
|---|---:|
| Completed requests | 40 / 40 |
| API request errors | 0 |
| Abstentions | 16 |
| Median API latency | 18.95 seconds |
| P95 API latency | 23.75 seconds |
| Citation-reference mismatches | 1 |

These metrics describe execution, latency, and response behavior. They do **not** establish that every generated answer was factually correct.

A separate provisional factual review identified both successful responses and incomplete or unsuccessful ones. Independent human verification remains necessary.

See [Gold-40 Evaluation](docs/GOLD40_EVALUATION.md) for methodology, findings, and limitations.

### Behavioral Testing

An earlier 20-case behavioral run passed 20 of 20 automated checks. These checks are distinct from factual accuracy.

## Known Limitations

- Broad questions may receive incomplete answers even when relevant evidence is retrieved.
- Cross-document regulatory and company-policy comparisons can result in abstentions.
- Citation identifiers alone do not prove that the underlying passages support every claim.
- Some company disclosures have incomplete temporal metadata.
- Guardrail rules can produce false positives.
- The 140 held-out questions have not yet been reported as a completed final evaluation.
- Performance depends on the selected generation provider and deployment environment.

These limitations are documented rather than hidden.

## Running Locally

### 1. Set Up Python

From the repository root on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure Generation

For Groq:

```powershell
$env:LENDLENS_GENERATION_PROVIDER = "groq"
$secureKey = Read-Host "Groq API key" -AsSecureString
$env:GROQ_API_KEY = [System.Net.NetworkCredential]::new("", $secureKey).Password
```

Alternatively, select the locally configured Ollama provider:

```powershell
$env:LENDLENS_GENERATION_PROVIDER = "ollama"
```

Ensure the selected Ollama model is available before starting the application.

### 3. Configure Qdrant

The application supports local Qdrant storage and a configured Qdrant Cloud instance.

For Qdrant Cloud, provide the relevant connection environment variables:

```powershell
$env:LENDLENS_QDRANT_URL = Read-Host "Qdrant URL"
$secureKey = Read-Host "Qdrant API key" -AsSecureString
$env:LENDLENS_QDRANT_API_KEY = [System.Net.NetworkCredential]::new("", $secureKey).Password
```

The database must already contain the required LendLens collection. Installing dependencies alone does not populate the knowledge base.

Avoid opening the same local Qdrant storage directory from multiple independent Python processes simultaneously.

### 4. Start the API

```powershell
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

### 5. Launch Streamlit

Open a separate terminal:

```powershell
streamlit run streamlit_app.py
```

### 6. Inspect API Health

Visit:

`http://127.0.0.1:8000/health`

## Repository Components

- `src/retrieval.py` ? hybrid retrieval, reranking and context expansion.
- `src/query_router.py` ? metadata-aware query routing.
- `src/generation.py` ? grounded-answer generation logic.
- `src/generation_providers.py` ? model-provider integration.
- `src/service.py` ? end-to-end question-answering orchestration.
- `api/main.py` ? FastAPI endpoints.
- `streamlit_app.py` ? user interface.
- `scripts/run_gold40.py` ? validation-run utility.
- `docs/GOLD40_EVALUATION.md` ? evaluation documentation.

## Responsible Use

LendLens is a research and educational system.

It should not be used as the sole authority for lending decisions, legal advice, compliance sign-off, or the interpretation of time-sensitive regulations.

Users should verify material requirements against current RBI publications and applicable company disclosures.

## Project Demonstration

A recorded product demonstration and screenshots can be added here.

## Development Status

**LendLens v1.0 ? evaluation completed; documentation and demonstration in progress.**
