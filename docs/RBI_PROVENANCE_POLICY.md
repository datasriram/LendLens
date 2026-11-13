# RBI provenance policy

LendLens separates **authority provenance** from **byte-acquisition provenance**.

- **Authority provenance** answers: Who issued this rule and what is its canonical source? For RBI Master Directions, authority is established by the RBI Master Directions index and the official `rbi.org.in` canonical URL.
- **Byte-acquisition provenance** answers: From which HTTP endpoint did the local corpus actually obtain the stored HTML bytes?

The preferred case is the same endpoint for both. When RBI's anti-automation/bootstrap response prevents local acquisition, LendLens may use a public snapshot only if the snapshot is deterministically validated against the official RBI index title and markers. This is recorded explicitly in each manifest record.

This policy avoids two bad practices:

1. disabling TLS verification to force a download; and
2. silently treating a third-party mirror as the authoritative regulator source.

Any snapshot that fails validation remains excluded from the index and appears as an acquisition failure for manual review.
