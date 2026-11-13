from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

# Use the Windows trust store where available. This is safer than verify=False
# and helps on Windows machines where antivirus / enterprise TLS interception
# causes certifi-only validation failures.
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

MASTER_INDEX_URL = "https://www.rbi.org.in/Scripts/BS_ViewMasterDirections.aspx"
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/147.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}

# Verified snapshot fallback. The RBI URL remains the canonical authority URL.
# A snapshot is accepted only after title/content validation against the official
# RBI Master Directions index entry. This is a provenance-preserving acquisition
# fallback, not a substitution of authority.
LITTDB_TEMPLATE = (
    "https://littdb.sfo2.cdn.digitaloceanspaces.com/"
    "litt/IN/RBI/notifications/RBI_{rid}.html"
)

CATEGORY_RULES = [
    ("internal_ombudsman", r"internal ombudsman"),
    ("kyc_aml", r"know your customer|\bkyc\b"),
    ("responsible_business_conduct", r"responsible business conduct"),
    ("outsourcing", r"managing risks in outsourcing"),
    ("financial_statements", r"financial statements"),
    ("wilful_default", r"wilful defaulters|willful defaulters"),
    ("stressed_assets", r"resolution of stressed assets"),
    ("asset_classification", r"income recognition.*asset classification|asset classification.*provisioning"),
    ("asset_liability_management", r"asset liability management"),
    ("investment_portfolio", r"classification, valuation and operation of investment portfolio"),
    ("securitisation", r"securitisation transactions"),
    ("transfer_credit_risk", r"transfer and distribution of credit risk"),
    ("concentration_risk", r"concentration risk management"),
    ("credit_risk", r"credit risk management"),
    ("credit_information", r"credit information reporting"),
    ("credit_cards", r"credit cards.*issuance and conduct"),
    ("credit_facilities", r"credit facilities"),
    ("public_deposits", r"acceptance of public deposits"),
    ("capital_adequacy", r"capital adequacy"),
    ("governance", r"governance\) directions|– governance| - governance"),
    ("financial_services", r"undertaking of financial services"),
    ("branch_authorisation", r"branch authorisation"),
    ("voluntary_amalgamation", r"voluntary amalgamation"),
    ("shareholding_control", r"acquisition of shareholding or control"),
    ("registration_scale_based", r"registration, exemptions and framework for scale based regulation"),
    ("microfinance", r"microfinance institution"),
    ("peer_to_peer", r"peer to peer lending platform"),
    ("account_aggregator", r"account aggregator"),
    ("climate_finance", r"climate finance"),
    ("fraud_risk", r"fraud risk management"),
    ("digital_payment_security", r"digital payment security controls"),
    ("cybersecurity", r"cybersecurity.*technology|technology.*risk.*resilience"),
    ("auditor_report", r"auditor.?s report"),
    ("statutory_audit", r"statutory audit"),
    ("internal_audit", r"internal audit function"),
    ("supervisory_returns", r"supervisory returns"),
    ("compliance", r"compliance function"),
    ("miscellaneous_supervisory", r"miscellaneous supervisory directions"),
    ("miscellaneous", r"miscellaneous\) directions"),
]

SUPERVISORY_PATTERNS = re.compile(
    r"auditor.?s report|miscellaneous supervisory|supervisory returns|statutory audit|"
    r"internal audit function|fraud risk management|digital payment security controls|"
    r"cybersecurity|compliance function",
    re.I,
)

TITLE_STOPWORDS = {
    "reserve", "bank", "of", "india", "non", "banking", "financial",
    "companies", "company", "directions", "direction", "2025", "2026",
    "updated", "as", "on", "the", "and", "for", "in", "to", "a", "an",
}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def visible_text(body: bytes) -> str:
    soup = BeautifulSoup(body, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "canvas", "form", "nav", "header", "footer", "aside"]):
        tag.decompose()
    return " ".join(soup.stripped_strings)


def visible_words(body: bytes) -> int:
    return len(re.findall(r"\b\w+\b", visible_text(body), flags=re.UNICODE))


def safe_name(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._")
    return text[:180] or "rbi_document"


def fetch(session: requests.Session, url: str, retries: int = 3, timeout: int = 60) -> requests.Response:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=timeout, allow_redirects=True)
            r.raise_for_status()
            return r
        except Exception as exc:
            last = exc
            time.sleep(1.25 * (attempt + 1))
    assert last is not None
    raise last


def canonical_rbi_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(("https", "www.rbi.org.in", parts.path, parts.query, ""))


def host_variants(url: str) -> list[str]:
    parts = urlsplit(canonical_rbi_url(url))
    out: list[str] = []
    for host in ["www.rbi.org.in", "m.rbi.org.in"]:
        candidate = urlunsplit(("https", host, parts.path, parts.query, ""))
        if candidate not in out:
            out.append(candidate)
    return out


def category_for(title: str) -> str:
    for category, pattern in CATEGORY_RULES:
        if re.search(pattern, title, flags=re.I):
            return category
    return "nbfc_regulation"


def source_id_for(url: str, title: str) -> str:
    qs = parse_qs(urlsplit(url).query)
    rid = (qs.get("id") or qs.get("Id") or [""])[0]
    if rid and str(rid).isdigit():
        return f"rbi_current_nbfc_{rid}"
    digest = hashlib.sha1((title + "|" + url).encode("utf-8")).hexdigest()[:12]
    return f"rbi_current_nbfc_{digest}"


def rbi_id_from_url(url: str) -> str:
    qs = parse_qs(urlsplit(url).query)
    rid = (qs.get("id") or qs.get("Id") or [""])[0]
    return str(rid) if str(rid).isdigit() else ""


def is_target_title(text: str) -> bool:
    t = re.sub(r"\s+", " ", text).strip()
    if "Directions" not in t:
        return False
    return "Non-Banking Financial Companies" in t


def discover(session: requests.Session) -> list[tuple[str, str]]:
    r = fetch(session, MASTER_INDEX_URL)
    soup = BeautifulSoup(r.content, "html.parser")
    found: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        title = " ".join(a.stripped_strings)
        if not is_target_title(title):
            continue
        url = urljoin(r.url, a["href"])
        host = (urlsplit(url).hostname or "").lower()
        if not host.endswith("rbi.org.in"):
            continue
        url = canonical_rbi_url(url)
        found[url] = title
    return sorted(found.items(), key=lambda x: x[1].lower())


def normalized_tokens(text: str) -> set[str]:
    toks = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in toks if len(t) > 2 and t not in TITLE_STOPWORDS}


def validate_snapshot(body: bytes, expected_title: str) -> tuple[bool, dict]:
    text = visible_text(body)
    word_count = len(re.findall(r"\b\w+\b", text, flags=re.UNICODE))
    expected = normalized_tokens(expected_title)
    actual = normalized_tokens(text[:12000])
    overlap = (len(expected & actual) / len(expected)) if expected else 0.0
    has_rbi = "reserve bank of india" in text.lower()
    has_directions = "directions" in text.lower()
    ok = word_count >= 120 and has_rbi and has_directions and overlap >= 0.60
    return ok, {
        "visible_words": word_count,
        "title_token_overlap": round(overlap, 4),
        "has_rbi_marker": has_rbi,
        "has_directions_marker": has_directions,
    }


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Discover current RBI NBFC Directions from the official RBI Master Directions index. "
            "Prefer RBI-hosted content; if RBI serves only a tiny anti-bot/bootstrap shell, use a "
            "strictly validated public snapshot while retaining the official RBI URL as canonical provenance."
        )
    )
    p.add_argument("--root", default=".")
    p.add_argument("--sleep", type=float, default=0.30)
    args = p.parse_args()

    root = Path(args.root).resolve()
    manifest = root / "data/manifests/download_manifest.jsonl"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    out_dir = root / "data/raw/Reserve_Bank_of_India/current_nbfc_directions"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = root / "data/reports/rbi_current_directions_acquisition_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    existing = read_jsonl(manifest)
    latest_by_sid: dict[str, dict] = {}
    for row in existing:
        sid = str(row.get("source_id", ""))
        if sid:
            latest_by_sid[sid] = row

    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)

    discovered = discover(session)
    appended: list[dict] = []
    successes = 0
    official_successes = 0
    verified_snapshot_successes = 0
    failures = 0
    skipped_success = 0

    print(f"Discovered {len(discovered)} current NBFC direction links from RBI master index")

    for canonical_url, title in discovered:
        sid = source_id_for(canonical_url, title)
        prior = latest_by_sid.get(sid)
        if prior and str(prior.get("status")) in {"downloaded", "duplicate_content"}:
            local = root / str(prior.get("local_path", ""))
            if local.exists():
                print("SKIP existing success:", sid)
                skipped_success += 1
                continue

        temporal_role = "current_supervisory_direction" if SUPERVISORY_PATTERNS.search(title) else "current_master_direction"
        category = category_for(title)
        errors: list[str] = []

        body: bytes | None = None
        final_url = ""
        acquisition_url = ""
        content_type = ""
        acquisition_mode = ""
        verification: dict = {}
        words = 0

        # 1) Preferred path: official RBI-owned host.
        best_official: tuple[int, requests.Response, str] | None = None
        for candidate in host_variants(canonical_url):
            try:
                resp = fetch(session, candidate)
                wc = visible_words(resp.content)
                if best_official is None or wc > best_official[0]:
                    best_official = (wc, resp, candidate)
                if wc >= 120:
                    break
            except Exception as exc:
                errors.append(f"official:{candidate}: {exc!r}")

        if best_official is not None and best_official[0] >= 120:
            words, resp, acquisition_url = best_official
            body = resp.content
            final_url = resp.url
            content_type = (resp.headers.get("content-type") or "").lower()
            acquisition_mode = "rbi_official_http"
            official_successes += 1
        else:
            # 2) Verified public snapshot fallback. This is only an acquisition fallback.
            # The official RBI URL discovered from RBI's Master Directions index remains
            # the canonical authority/source URL in the manifest.
            rid = rbi_id_from_url(canonical_url)
            if rid:
                snapshot_url = LITTDB_TEMPLATE.format(rid=rid)
                try:
                    snap = fetch(session, snapshot_url)
                    ok, verification = validate_snapshot(snap.content, title)
                    if ok:
                        body = snap.content
                        words = int(verification["visible_words"])
                        final_url = snap.url
                        acquisition_url = snapshot_url
                        content_type = (snap.headers.get("content-type") or "text/html").lower()
                        acquisition_mode = "verified_snapshot_fallback_littdb"
                        verified_snapshot_successes += 1
                    else:
                        errors.append(
                            "snapshot_validation_failed:"
                            + json.dumps(verification, ensure_ascii=False)
                        )
                except Exception as exc:
                    errors.append(f"snapshot:{snapshot_url}: {exc!r}")
            else:
                errors.append("no_numeric_rbi_id_for_snapshot_fallback")

        if body is None:
            failures += 1
            best_words = best_official[0] if best_official else 0
            rec = {
                "source_id": sid,
                "publisher": "Reserve Bank of India",
                "entity": "RBI",
                "category": category,
                "title": title,
                "requested_url": canonical_url,
                "canonical_source_url": canonical_url,
                "authority": "regulator",
                "temporal_role": temporal_role,
                "acquisition_mode": "rbi_v1_3_3_failed",
                "status": "failed",
                "error": " | ".join(errors) if errors else f"low_substantive_text_words={best_words}",
                "attempted_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            appended.append(rec)
            print("ERR ", sid, rec["error"][:200])
            time.sleep(args.sleep)
            continue

        digest = hashlib.sha256(body).hexdigest()
        path = out_dir / (safe_name(sid + "_" + title) + ".html")
        path.write_bytes(body)

        rec = {
            "source_id": sid,
            "publisher": "Reserve Bank of India",
            "entity": "RBI",
            "category": category,
            "title": title,
            "requested_url": canonical_url,
            "canonical_source_url": canonical_url,
            "final_url": final_url,
            "acquisition_url": acquisition_url,
            "content_type": content_type,
            "source_kind": "html",
            "bytes": len(body),
            "sha256": digest,
            "local_path": str(path.relative_to(root)),
            "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "downloaded",
            "temporal_role": temporal_role,
            "authority": "regulator",
            "master_index_url": MASTER_INDEX_URL,
            "visible_word_count_at_download": words,
            "acquisition_mode": acquisition_mode,
            "provenance": {
                "authority_url": canonical_url,
                "discovered_from_official_rbi_master_index": True,
                "content_acquired_from_official_rbi_host": acquisition_mode == "rbi_official_http",
                "snapshot_fallback_used": acquisition_mode.startswith("verified_snapshot_fallback"),
                "snapshot_validation": verification or None,
            },
            "notes": (
                "Canonical authority is the official RBI Master Directions URL. "
                "When RBI's automated HTTP response is only a non-substantive bootstrap shell, "
                "the local corpus may use a public snapshot only after deterministic title/content "
                "validation against the official RBI Master Directions index."
            ),
        }
        appended.append(rec)
        successes += 1
        tag = "OFFICIAL" if acquisition_mode == "rbi_official_http" else "SNAPSHOT-VERIFIED"
        print(f"OK   {sid} {tag} {category} {words} words")
        time.sleep(args.sleep)

    with manifest.open("a", encoding="utf-8") as f:
        for rec in appended:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    report = {
        "master_index_url": MASTER_INDEX_URL,
        "discovered_current_nbfc_direction_links": len(discovered),
        "new_successful_downloads": successes,
        "official_rbi_host_successes": official_successes,
        "verified_snapshot_successes": verified_snapshot_successes,
        "failed_downloads": failures,
        "skipped_existing_successes": skipped_success,
        "appended_manifest_records": len(appended),
        "provenance_policy": (
            "Official RBI Master Directions index determines authority/title/canonical URL. "
            "RBI-hosted content is preferred. If RBI serves only a tiny bootstrap shell to local automation, "
            "a public snapshot is accepted only after deterministic title/content validation and is marked "
            "explicitly as a snapshot fallback in the manifest."
        ),
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("Report:", report_path)


if __name__ == "__main__":
    main()
