# Why v1.3 exists

The v1.2 report showed that corpus volume was already adequate, but regulatory coverage did not improve: only two RBI documents reached the curated index. This was not a reason to collect more random company pages. It was a source-acquisition design problem.

RBI reorganised a large part of the NBFC rulebook into consolidated NBFC-specific Directions dated November 28, 2025 and subsequent 2026 supervisory Directions. For a regulatory-intelligence project, the current official Master Directions index is a better acquisition anchor than a static list of older circular URLs.

v1.3 therefore treats the RBI Master Directions index as an authoritative discovery source and downloads the linked NBFC directions from RBI-owned domains. The raw corpus remains immutable and auditable.

The company corpus remains valuable for comparing regulatory requirements with public NBFC policies and disclosures, but it is balanced in the first experimental core so one crawler-rich website cannot dominate retrieval benchmarks.

Unresolved metadata remains visible in a manual review queue. The pipeline does not invent a legal status or a policy category merely to pass a metric.
