# LendLens ? Gold-40 Evaluation

Generated: 2026-11-16 09:17 UTC

## Evaluation setup

- Dataset: 40 verified validation questions.
- Dataset role: validation, not held-out final test.
- Generation provider: Groq (as configured during the run).
- Retrieval: hybrid dense/sparse search with reranking and metadata routing.
- Raw results: `reports/gold40_raw_results.json`.
- Gold benchmark: `LendLens_Evaluation_Benchmark_v3_Gold40_Verified.xlsx` (maintained separately).

## Execution metrics

- Completed requests: 40/40.
- Request errors: 0.
- Abstained responses: 16.
- Guardrail-blocked responses: 3.
- Median API latency: 18.95 seconds.
- P95 API latency: 23.75 seconds.
- Minimum / maximum latency: 0.00 / 30.83 seconds.

## Question categories

- Adversarial / safety: 4
- Company policy lookup: 5
- Cross-document: 4
- Direct regulatory lookup: 7
- Exact terminology / acronym: 3
- Multi-hop / reasoning: 3
- Numeric / threshold: 4
- RBI vs company comparison: 4
- Temporal / version: 3
- Unanswerable / abstention: 3

## Evaluation findings

- API execution success does not imply factual accuracy.
- Broad regulatory answers can omit important conditions, thresholds and timelines.
- Some cross-document comparison questions resulted in abstentions.
- LL-144 exposed a guardrail false positive: rejection of a customer complaint was mistaken for a loan-rejection decision.
- LL-174 exposed a guardrail explanation problem for prompt-injection handling.
- Some company-policy answers need stronger source-version and temporal qualification.

## Citation-reference validation

Responses with citations absent from returned source metadata: 1.

- LL-052: S4, S5

**Limitation:** This check verifies citation identifiers only. It does not establish that retrieved passages support every claim.

## Factual scoring

The separate Gold-40 evaluation workbook contains the provisional question-level correctness review. Those scores require human verification before being represented as audited accuracy.

## Known limitations

1. Answers can be incomplete even when the correct regulatory document is retrieved.
2. Multi-document comparisons can fail because evidence is not assembled adequately.
3. Source identifiers alone are insufficient for citation-faithfulness scoring.
4. Company disclosures may have unknown or outdated temporal metadata.
5. Guardrail behavior can include false positives.

## Dataset integrity

The Gold-40 responses are retained as a frozen validation snapshot.
The remaining 140 benchmark questions are reserved for held-out evaluation.
No gold-answer content was added to the retrieval system during this reporting step.
