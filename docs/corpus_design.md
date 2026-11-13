# Corpus design

## Objective

Build a reproducible real-world Indian NBFC corpus suitable for production-RAG experiments, not a toy document-chat demo.

## Source hierarchy

1. **RBI regulatory material** — highest authority for regulatory questions.
2. **NBFC board/company policies and customer disclosures** — organisation-specific implementation and customer conduct.
3. **Audited annual reports / financial statements** — company-specific risk, financial and governance evidence.
4. **Historical/superseded versions** — retained deliberately to test temporal and version-aware retrieval.

## Why keep old versions?

Deleting superseded documents makes the retrieval task unrealistically easy. A serious policy RAG system must distinguish a semantically relevant old rule from the currently applicable one. Metadata therefore records `status`, effective dates, supersession links and authority.

## Raw-store rule

Files in `data/raw/` are immutable source copies. Do not manually edit them. Derived text, chunks or tables belong in later `normalized/` and index layers.

## Real-world constraints

- Public websites may change paths or block automated retrieval.
- Some documents are HTML rather than PDF.
- Annual reports are large and table-heavy.
- Policies can be silently updated in place.
- A source URL alone is insufficient provenance; record retrieval time and SHA-256.
- The downloader records failures instead of hiding them. Failed acquisition is a legitimate corpus-engineering issue to resolve.
