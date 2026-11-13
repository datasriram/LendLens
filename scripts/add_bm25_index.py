from __future__ import annotations

from qdrant_client import QdrantClient, models

from src.sparse_embeddings import BM25Embedder


COLLECTION = "lendlens_core_dense_v1"
BATCH_SIZE = 256


def main():

    print("=" * 100)
    print("LENDLENS — ADD BM25 SPARSE INDEX")
    print("=" * 100)

    client = QdrantClient(
        path="qdrant_core_data"
    )

    info = client.get_collection(
        COLLECTION
    )

    sparse_config = (
        info.config.params.sparse_vectors
        or {}
    )

    if "bm25" not in sparse_config:

        print("\nCreating BM25 sparse vector field...")

        client.create_vector_name(
            collection_name=COLLECTION,
            vector_name="bm25",
            vector_name_config=models.SparseVectorNameConfig(
                sparse=models.SparseVectorConfig(
                    modifier=models.Modifier.IDF,
                )
            ),
        )

    else:

        print("\nBM25 vector field already exists.")

    embedder = BM25Embedder(
        batch_size=BATCH_SIZE
    )

    offset = None
    updated = 0

    while True:

        points, next_offset = client.scroll(
            collection_name=COLLECTION,
            limit=BATCH_SIZE,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        if not points:
            break

        texts = [
            (point.payload or {}).get(
                "text",
                "",
            )
            for point in points
        ]

        sparse_vectors = (
            embedder.embed_documents(texts)
        )

        updates = [
            models.PointVectors(
                id=point.id,
                vector={
                    "bm25": sparse_vector
                },
            )
            for point, sparse_vector
            in zip(
                points,
                sparse_vectors,
            )
        ]

        client.update_vectors(
            collection_name=COLLECTION,
            points=updates,
            wait=True,
        )

        updated += len(points)

        print(
            f"BM25 indexed: {updated}"
        )

        if next_offset is None:
            break

        offset = next_offset

    print("\n" + "=" * 100)
    print("BM25 BACKFILL COMPLETE")
    print("=" * 100)

    print("Points updated:", updated)


if __name__ == "__main__":
    main()
