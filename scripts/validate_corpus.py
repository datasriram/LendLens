from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pymupdf


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    raw = root / "data" / "raw"
    report = root / "data" / "reports" / "corpus_validation.json"
    report.parent.mkdir(parents=True, exist_ok=True)

    files = [p for p in raw.rglob("*") if p.is_file() and p.name != ".gitkeep"]
    pdf_pages = 0
    pdf_count = 0
    html_count = 0
    invalid: list[str] = []
    hashes: dict[str, str] = {}
    duplicates: list[list[str]] = []

    for path in files:
        digest = sha256_file(path)
        rel = str(path.relative_to(root))
        if digest in hashes:
            duplicates.append([rel, hashes[digest]])
        else:
            hashes[digest] = rel

        head = path.read_bytes()[:8]
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            pdf_count += 1
            if not head.startswith(b"%PDF-"):
                invalid.append(rel)
                continue
            try:
                with pymupdf.open(path) as doc:
                    pdf_pages += len(doc)
            except Exception:
                invalid.append(rel)
        elif suffix in {".html", ".htm"}:
            html_count += 1

    out = {
        "documents": len(files),
        "pdfs": pdf_count,
        "html_files": html_count,
        "pdf_pages": pdf_pages,
        "bytes": sum(p.stat().st_size for p in files),
        "unique_sha256": len(hashes),
        "duplicate_file_count": len(duplicates),
        "duplicates": duplicates,
        "invalid_files": invalid,
    }
    report.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
