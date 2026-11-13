from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.parsing import ParsedDocument, parse_pdf, parse_html


IMPORTANT_METADATA_FIELDS = [
    "source_id",
    "title",
    "publisher",
    "category",
    "authority",
    "temporal_role",
    "source_kind",
    "source_url",
    "url",
]


def load_manifest(
    manifest_path: str | Path = "data/manifests/index_manifest.jsonl",
) -> list[dict[str, Any]]:

    manifest_path = Path(manifest_path)

    records = []

    for line in manifest_path.read_text(
        encoding="utf-8"
    ).splitlines():

        if not line.strip():
            continue

        records.append(
            json.loads(line)
        )

    return records


def build_metadata(
    record: dict[str, Any],
) -> dict[str, Any]:

    metadata = {}

    for field in IMPORTANT_METADATA_FIELDS:

        value = record.get(field)

        if value is not None:
            metadata[field] = value

    return metadata


def parse_manifest_record(
    record: dict[str, Any],
) -> list[ParsedDocument]:

    local_path = record.get("local_path")

    if not local_path:
        return []

    path = Path(local_path)

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    metadata = build_metadata(record)

    suffix = path.suffix.lower()

    if suffix == ".pdf":

        return parse_pdf(
            path,
            metadata=metadata,
        )

    if suffix in {
        ".html",
        ".htm",
    }:

        return parse_html(
            path,
            metadata=metadata,
        )

    return []
