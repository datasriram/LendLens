from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

UA = "LendLens-Academic-Corpus-Builder/1.1 (final-year-project; public documents only)"


def safe_name(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._")
    return text[:180] or "document"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(session: requests.Session, url: str, timeout: int = 45, retries: int = 3) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = session.get(url, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            return response
        except Exception as exc:  # intentionally retained in manifest by caller
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def save_response(
    root: Path,
    *,
    source_id: str,
    publisher: str,
    category: str,
    title: str,
    url: str,
    response: requests.Response,
    parent_seed: str | None = None,
    extra_metadata: dict[str, str] | None = None,
) -> dict[str, object]:
    content_type = (response.headers.get("content-type") or "").lower()
    body = response.content
    digest = sha256_bytes(body)
    is_pdf = "pdf" in content_type or body[:5] == b"%PDF-"
    extension = ".pdf" if is_pdf else ".html"

    entity_dir = safe_name(publisher)
    out_dir = root / "data" / "raw" / entity_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = safe_name(source_id + "_" + title) + extension
    path = out_dir / filename
    path.write_bytes(body)

    record: dict[str, object] = {
        "source_id": source_id,
        "parent_seed_id": parent_seed or "",
        "publisher": publisher,
        "category": category,
        "title": title,
        "requested_url": url,
        "final_url": response.url,
        "content_type": content_type,
        "source_kind": "pdf" if is_pdf else "html",
        "bytes": len(body),
        "sha256": digest,
        "local_path": str(path.relative_to(root)),
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "downloaded",
    }
    if extra_metadata:
        record.update({k: v for k, v in extra_metadata.items() if v not in (None, "")})
    return record


def same_allowed_domain(url: str, allowed: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    allowed = allowed.lower().lstrip(".")
    return host == allowed or host.endswith("." + allowed)


def discover_links(
    html: bytes,
    base_url: str,
    allowed_domain: str,
    include_regex: str,
    max_links: int,
) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    pattern = re.compile(include_regex)
    seen: set[str] = set()
    found: list[tuple[str, str]] = []

    base_without_fragment = urldefrag(base_url).url
    generic_labels = {
        "skip to main content", "home", "reach us", "others", "contact us",
        "about us", "privacy", "login", "sign in", "menu",
    }

    for anchor in soup.find_all("a", href=True):
        raw_href = str(anchor["href"]).strip()
        if not raw_href or raw_href.startswith("#"):
            continue
        href = urldefrag(urljoin(base_url, raw_href)).url
        text = " ".join(anchor.stripped_strings).strip()
        text_norm = re.sub(r"\s+", " ", text).lower()
        if text_norm in generic_labels:
            continue
        if href == base_without_fragment:
            continue
        if not same_allowed_domain(href, allowed_domain):
            continue

        # Match against meaningful link text + target path, not the entire current page URL.
        # This avoids a seed URL containing the word "policy" causing every fragment/nav link
        # on that page to be downloaded as if it were a policy document.
        parsed = urlparse(href)
        candidate = text + " " + parsed.path + " " + parsed.query
        if not pattern.search(candidate):
            continue
        if href in seen:
            continue
        seen.add(href)
        found.append((href, text or Path(parsed.path).name))
        if len(found) >= max_links:
            break
    return found


def failure_record(row: dict[str, str], error: Exception, *, status: str = "failed") -> dict[str, object]:
    return {
        "source_id": row.get("source_id") or row.get("seed_id") or "unknown",
        "publisher": row.get("publisher", ""),
        "category": row.get("category", ""),
        "title": row.get("title", ""),
        "requested_url": row.get("url", ""),
        "authority": row.get("authority", ""),
        "temporal_role": row.get("temporal_role", ""),
        "status": status,
        "error": repr(error),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and discover public LendLens corpus sources.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--direct-only", action="store_true", help="Skip collection-page discovery.")
    parser.add_argument("--sleep", type=float, default=0.8, help="Delay between requests in seconds.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    (root / "data" / "raw").mkdir(parents=True, exist_ok=True)
    (root / "data" / "manifests").mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": UA})

    records: list[dict[str, object]] = []
    seen_hashes: dict[str, str] = {}

    with open(root / "config" / "direct_sources.csv", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                response = fetch(session, row["url"])
                metadata = {
                    "entity": row.get("entity", ""),
                    "source_format_catalogued": row.get("source_format", ""),
                    "temporal_role": row.get("temporal_role", ""),
                    "authority": row.get("authority", ""),
                    "notes": row.get("notes", ""),
                    "acquisition_mode": "curated_direct",
                }
                record = save_response(
                    root,
                    source_id=row["source_id"],
                    publisher=row["publisher"],
                    category=row["category"],
                    title=row["title"],
                    url=row["url"],
                    response=response,
                    extra_metadata=metadata,
                )
                digest = str(record["sha256"])
                if digest in seen_hashes:
                    record["status"] = "duplicate_content"
                    record["duplicate_of"] = seen_hashes[digest]
                else:
                    seen_hashes[digest] = row["source_id"]
                records.append(record)
                print("OK  ", row["source_id"], record["bytes"])
            except Exception as exc:
                records.append(failure_record(row, exc))
                print("ERR ", row["source_id"], exc)
            time.sleep(args.sleep)

    if not args.direct_only:
        with open(root / "config" / "collection_seeds.csv", encoding="utf-8", newline="") as handle:
            for seed in csv.DictReader(handle):
                try:
                    seed_response = fetch(session, seed["url"])
                    seed_record = save_response(
                        root,
                        source_id=seed["seed_id"],
                        publisher=seed["publisher"],
                        category="collection_page",
                        title=seed["seed_id"],
                        url=seed["url"],
                        response=seed_response,
                        parent_seed=seed["seed_id"],
                        extra_metadata={
                            "acquisition_mode": "collection_seed",
                            "notes": seed.get("notes", ""),
                        },
                    )
                    records.append(seed_record)

                    links = discover_links(
                        seed_response.content,
                        seed_response.url,
                        seed["domain"],
                        seed["include_regex"],
                        int(seed["max_links"]),
                    )
                    for index, (url, text) in enumerate(links, start=1):
                        source_id = f"{seed['seed_id']}_discovered_{index:03d}"
                        try:
                            response = fetch(session, url)
                            authority = "regulator" if seed["publisher"] == "Reserve Bank of India" else "company_public_source"
                            record = save_response(
                                root,
                                source_id=source_id,
                                publisher=seed["publisher"],
                                category="discovered",
                                title=text,
                                url=url,
                                response=response,
                                parent_seed=seed["seed_id"],
                                extra_metadata={
                                    "authority": authority,
                                    "acquisition_mode": "discovered_from_official_collection",
                                },
                            )
                            digest = str(record["sha256"])
                            if digest in seen_hashes:
                                record["status"] = "duplicate_content"
                                record["duplicate_of"] = seen_hashes[digest]
                            else:
                                seen_hashes[digest] = source_id
                            records.append(record)
                            print("DISC", source_id, text[:80])
                        except Exception as exc:
                            records.append(
                                {
                                    "source_id": source_id,
                                    "parent_seed_id": seed["seed_id"],
                                    "publisher": seed["publisher"],
                                    "title": text,
                                    "requested_url": url,
                                    "status": "failed",
                                    "error": repr(exc),
                                }
                            )
                        time.sleep(args.sleep)
                except Exception as exc:
                    row = dict(seed)
                    row["source_id"] = seed["seed_id"]
                    records.append(failure_record(row, exc, status="seed_failed"))

    manifest = root / "data" / "manifests" / "download_manifest.jsonl"
    with open(manifest, "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Wrote {len(records)} records -> {manifest}")


if __name__ == "__main__":
    main()
