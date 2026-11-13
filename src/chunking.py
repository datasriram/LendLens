from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.parsing import ParsedDocument


@dataclass
class Chunk:
    text: str
    metadata: dict[str, Any]


class PageAwareChunker:

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n\n",
                "\n",
                ". ",
                " ",
                "",
            ],
        )

    def split(
        self,
        documents: list[ParsedDocument],
    ) -> list[Chunk]:

        chunks: list[Chunk] = []

        global_chunk_index = 0

        for doc_index, document in enumerate(documents):

            split_texts = self.splitter.split_text(
                document.text
            )

            for local_index, text in enumerate(split_texts):

                text = text.strip()

                if not text:
                    continue

                metadata = {
                    **document.metadata,
                    "document_unit_index": doc_index,
                    "chunk_index": global_chunk_index,
                    "chunk_index_on_page": local_index,
                    "chunk_size_setting": self.chunk_size,
                    "chunk_overlap_setting": self.chunk_overlap,
                }

                chunks.append(
                    Chunk(
                        text=text,
                        metadata=metadata,
                    )
                )

                global_chunk_index += 1

        return chunks
