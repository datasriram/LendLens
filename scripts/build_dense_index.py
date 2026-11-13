from __future__ import annotations

from src.corpus import (
    load_manifest,
    parse_manifest_record,
)
from src.chunking import PageAwareChunker
from src.embeddings import BGEEmbedder
from src.vector_store import DenseVectorStore


BATCH_SIZE = 256


def main():

    print("=" * 100)
    print("LENDLENS — BUILD DENSE INDEX")
    print("=" * 100)

    records = load_manifest("data/manifests/core_index_manifest.jsonl")

    print("\nManifest documents:", len(records))

    chunker = PageAwareChunker(
        chunk_size=1000,
        chunk_overlap=150,
    )

    embedder = BGEEmbedder()

    store = DenseVectorStore(
        path="qdrant_core_data",
        collection_name="lendlens_core_dense_v1",
    )

    print("\nResetting collection...")

    store.reset_collection()

    point_id = 0

    total_parsed_units = 0
    total_chunks = 0

    success_docs = 0
    failed_docs = 0

    pending_chunks = []


    def flush():

        nonlocal point_id
        nonlocal total_chunks
        nonlocal pending_chunks

        if not pending_chunks:
            return

        texts = [
            chunk.text
            for chunk in pending_chunks
        ]

        vectors = embedder.embed_documents(
            texts
        )

        ids = list(
            range(
                point_id,
                point_id + len(pending_chunks),
            )
        )

        payloads = []

        for chunk in pending_chunks:

            payload = {
                **chunk.metadata,
                "text": chunk.text,
            }

            payloads.append(payload)

        store.upload_batch(
            ids=ids,
            vectors=vectors,
            payloads=payloads,
        )

        point_id += len(pending_chunks)
        total_chunks += len(pending_chunks)

        pending_chunks = []


    for index, record in enumerate(
        records,
        start=1,
    ):

        title = (
            record.get("title")
            or record.get("local_path")
            or "Unknown"
        )

        try:

            parsed = parse_manifest_record(
                record
            )

            if not parsed:
                print(
                    f"[SKIP {index}/{len(records)}] "
                    f"{title}"
                )

                continue

            chunks = chunker.split(
                parsed
            )

            total_parsed_units += len(parsed)

            success_docs += 1

            pending_chunks.extend(
                chunks
            )

            while len(pending_chunks) >= BATCH_SIZE:

                batch = pending_chunks[:BATCH_SIZE]

                pending_chunks = (
                    pending_chunks[BATCH_SIZE:]
                )

                texts = [
                    chunk.text
                    for chunk in batch
                ]

                vectors = embedder.embed_documents(
                    texts
                )

                ids = list(
                    range(
                        point_id,
                        point_id + len(batch),
                    )
                )

                payloads = [
                    {
                        **chunk.metadata,
                        "text": chunk.text,
                    }
                    for chunk in batch
                ]

                store.upload_batch(
                    ids=ids,
                    vectors=vectors,
                    payloads=payloads,
                )

                point_id += len(batch)
                total_chunks += len(batch)

            print(
                f"[OK {index}/{len(records)}] "
                f"{title} | "
                f"units={len(parsed)} "
                f"chunks={len(chunks)}"
            )

        except Exception as exc:

            failed_docs += 1

            print(
                f"[FAIL {index}/{len(records)}] "
                f"{title}"
            )

            print(
                f"       {type(exc).__name__}: "
                f"{exc}"
            )


    flush()


    print("\n" + "=" * 100)
    print("INDEX BUILD COMPLETE")
    print("=" * 100)

    print("Successful documents:", success_docs)
    print("Failed documents:", failed_docs)

    print(
        "Parsed document units:",
        total_parsed_units,
    )

    print(
        "Chunks indexed:",
        total_chunks,
    )

    print(
        "Qdrant point count:",
        store.count(),
    )


if __name__ == "__main__":
    main()

