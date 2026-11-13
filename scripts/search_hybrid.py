from __future__ import annotations

from qdrant_client import QdrantClient, models

from src.embeddings import BGEEmbedder
from src.sparse_embeddings import BM25Embedder


COLLECTION = "lendlens_core_dense_v1"


def main():

    client = QdrantClient(
        path="qdrant_core_data"
    )

    dense = BGEEmbedder()
    sparse = BM25Embedder()

    print("=" * 100)
    print("LENDLENS — HYBRID RETRIEVAL")
    print("=" * 100)

    while True:

        query = input(
            "\nAsk a question (or type exit): "
        ).strip()

        if query.lower() in {
            "exit",
            "quit",
        }:
            break

        if not query:
            continue

        dense_vector = (
            dense.embed_query(query)
        )

        sparse_vector = (
            sparse.embed_query(query)
        )

        response = client.query_points(
            collection_name=COLLECTION,

            prefetch=[
                # Dense semantic candidates
                models.Prefetch(
                    query=dense_vector,
                    limit=20,
                ),

                # BM25 lexical candidates
                models.Prefetch(
                    query=sparse_vector,
                    using="bm25",
                    limit=20,
                ),
            ],

            # Reciprocal Rank Fusion
            query=models.FusionQuery(
                fusion=models.Fusion.RRF
            ),

            limit=5,
            with_payload=True,
        )

        print("\nTOP 5 HYBRID RESULTS\n")

        for rank, result in enumerate(
            response.points,
            start=1,
        ):

            payload = result.payload or {}

            print("=" * 100)

            print(
                f"RANK {rank} | "
                f"FUSION SCORE {result.score:.4f}"
            )

            print(
                "TITLE:",
                payload.get("title"),
            )

            print(
                "PUBLISHER:",
                payload.get("publisher"),
            )

            print(
                "AUTHORITY:",
                payload.get("authority"),
            )

            print(
                "CATEGORY:",
                payload.get("category"),
            )

            print(
                "TEMPORAL:",
                payload.get("temporal_role"),
            )

            print(
                "PAGE:",
                payload.get("page_number"),
            )

            print("\nTEXT:\n")

            print(
                payload.get(
                    "text",
                    "",
                )[:1400]
            )

            print()


if __name__ == "__main__":
    main()
