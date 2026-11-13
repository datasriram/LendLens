from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf
from bs4 import BeautifulSoup


@dataclass
class ParsedDocument:
    text: str
    metadata: dict[str, Any]


# ============================================================
# PDF PARSER
# ============================================================

def parse_pdf(
    path: str | Path,
    metadata: dict[str, Any] | None = None,
) -> list[ParsedDocument]:

    path = Path(path)
    base_metadata = metadata.copy() if metadata else {}

    documents: list[ParsedDocument] = []

    with pymupdf.open(path) as pdf:

        for page_index, page in enumerate(pdf):

            # sort=True asks PyMuPDF to return text in a more natural
            # top-to-bottom / left-to-right reading order.
            text = page.get_text(
                "text",
                sort=True,
            )

            text = clean_text(text)

            if not text:
                continue

            page_metadata = {
                **base_metadata,
                "source_type": "pdf",
                "file_name": path.name,
                "local_path": str(path),
                "page_index": page_index,
                "page_number": page_index + 1,
                "total_pages": len(pdf),
            }

            documents.append(
                ParsedDocument(
                    text=text,
                    metadata=page_metadata,
                )
            )

    return documents


# ============================================================
# HTML PARSER
# ============================================================

def parse_html(
    path: str | Path,
    metadata: dict[str, Any] | None = None,
) -> list[ParsedDocument]:

    path = Path(path)
    base_metadata = metadata.copy() if metadata else {}

    html = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    soup = BeautifulSoup(html, "html.parser")

    # Remove content that should never become RAG evidence.
    for tag in soup.find_all(
        [
            "script",
            "style",
            "noscript",
            "nav",
            "header",
            "footer",
            "form",
            "button",
            "select",
            "option",
        ]
    ):
        tag.decompose()

    # Prefer semantically meaningful content containers.
    main = (
        soup.find("article")
        or soup.select_one("main#content")
        or soup.find("main")
        or soup.select_one(".ckedior-content")
        or soup.body
    )

    if main is None:
        return []

    title = ""

    if soup.title:
        title = clean_text(
            soup.title.get_text(" ", strip=True)
        )

    # Newlines help preserve some structural boundaries,
    # which will later help the chunker.
    text = main.get_text(
        separator="\n",
        strip=True,
    )

    text = clean_text(text)

    if not text:
        return []

    html_metadata = {
        **base_metadata,
        "source_type": "html",
        "file_name": path.name,
        "local_path": str(path),
        "page_title": title,
    }

    return [
        ParsedDocument(
            text=text,
            metadata=html_metadata,
        )
    ]


# ============================================================
# COMMON CLEANING
# ============================================================

def clean_text(text: str) -> str:

    lines = []

    for line in text.splitlines():

        line = " ".join(
            line.split()
        ).strip()

        if line:
            lines.append(line)

    return "\n".join(lines)
