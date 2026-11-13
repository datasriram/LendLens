# Why the RBI acquisition pipeline has a browser fallback

The official RBI Master Directions index is discoverable through ordinary HTTP requests, but some individual direction pages deliver only a very small bootstrap/JavaScript document to a non-browser client. The same official URL renders the complete regulatory text in a browser.

For corpus integrity, LendLens therefore uses a two-stage acquisition strategy:

1. **Requests first** — cheap, deterministic and easy to audit.
2. **Rendered browser fallback** — only when the official response is clearly non-substantive.

The browser fallback uses the user's installed Microsoft Edge, preserves the official RBI URL, saves the rendered HTML, computes SHA-256, and records the acquisition mode in the manifest.

This is an acquisition-layer concern only. The downstream curation, metadata enrichment, chunking and retrieval pipelines remain unchanged.
