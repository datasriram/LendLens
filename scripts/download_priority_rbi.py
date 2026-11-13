from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

UA = "LendLens-Academic-Corpus-Builder/1.2 (public official documents only)"


def safe_name(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._")
    return text[:180] or "document"


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def fetch(session: requests.Session, url: str, retries: int = 3, timeout: int = 45) -> requests.Response:
    last = None
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=timeout, allow_redirects=True)
            r.raise_for_status()
            return r
        except Exception as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    assert last is not None
    raise last


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--catalog", default="config/rbi_priority_sources_v1_2.csv")
    parser.add_argument("--sleep", type=float, default=0.8)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    catalog = root / args.catalog
    manifest = root / "data/manifests/download_manifest.jsonl"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    out_dir = root / "data/raw/Reserve_Bank_of_India"
    out_dir.mkdir(parents=True, exist_ok=True)

    existing = read_jsonl(manifest)
    seen_source_ids = {str(r.get("source_id", "")) for r in existing}
    seen_urls = {str(r.get("requested_url", "")) for r in existing}
    seen_hashes = {str(r.get("sha256", "")): str(r.get("source_id", "")) for r in existing if r.get("sha256")}

    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    appended: list[dict] = []

    with catalog.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            sid = row["source_id"]
            if sid in seen_source_ids:
                print("SKIP source_id already present:", sid)
                continue
            # Do not skip solely on URL: v1.2 may intentionally retry a source whose older acquisition failed.
            try:
                resp = fetch(session, row["url"])
                body = resp.content
                ctype = (resp.headers.get("content-type") or "").lower()
                is_pdf = "pdf" in ctype or body[:5] == b"%PDF-"
                ext = ".pdf" if is_pdf else ".html"
                digest = hashlib.sha256(body).hexdigest()
                path = out_dir / (safe_name(sid + "_" + row["title"]) + ext)
                path.write_bytes(body)
                rec = {
                    "source_id": sid,
                    "publisher": row["publisher"],
                    "entity": row["entity"],
                    "category": row["category"],
                    "title": row["title"],
                    "requested_url": row["url"],
                    "final_url": resp.url,
                    "content_type": ctype,
                    "source_kind": "pdf" if is_pdf else "html",
                    "bytes": len(body),
                    "sha256": digest,
                    "local_path": str(path.relative_to(root)),
                    "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                    "status": "downloaded",
                    "source_format_catalogued": row["source_format"],
                    "temporal_role": row["temporal_role"],
                    "authority": row["authority"],
                    "notes": row["notes"],
                    "acquisition_mode": "priority_regulatory_v1_2",
                }
                if digest in seen_hashes:
                    rec["status"] = "duplicate_content"
                    rec["duplicate_of"] = seen_hashes[digest]
                else:
                    seen_hashes[digest] = sid
                appended.append(rec)
                print("OK  ", sid, len(body), rec["status"])
            except Exception as exc:
                appended.append({
                    "source_id": sid,
                    "publisher": row["publisher"],
                    "entity": row["entity"],
                    "category": row["category"],
                    "title": row["title"],
                    "requested_url": row["url"],
                    "authority": row["authority"],
                    "temporal_role": row["temporal_role"],
                    "acquisition_mode": "priority_regulatory_v1_2",
                    "status": "failed",
                    "error": repr(exc),
                })
                print("ERR ", sid, exc)
            time.sleep(args.sleep)

    with manifest.open("a", encoding="utf-8") as f:
        for rec in appended:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Appended {len(appended)} records -> {manifest}")


if __name__ == "__main__":
    main()
