from __future__ import annotations

from qdrant_client import (
    QdrantClient,
    models,
)

from src.embeddings import BGEEmbedder
from src.sparse_embeddings import BM25Embedder
from src.query_router import route_query


COLLECTION = "lendlens_core_dense_v1"


def main():

    client = QdrantClient(
        path="qdrant_core_data"
    )

    dense = BGEEmbedder()
    sparse = BM25Embedder()

    print("=" * 100)
    print("LENDLENS — METADATA-AWARE HYBRID RETRIEVAL")
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

        routing = route_query(query)

        print("\nROUTING DECISION:")
        print(routing.details)

        dense_vector = dense.embed_query(
            query
        )

        sparse_vector = sparse.embed_query(
            query
        )

        response = client.query_points(
            collection_name=COLLECTION,

            prefetch=[
                models.Prefetch(
                    query=dense_vector,
                    filter=routing.query_filter,
                    limit=30,
                ),

                models.Prefetch(
                    query=sparse_vector,
                    using="bm25",
                    filter=routing.query_filter,
                    limit=30,
                ),
            ],

            query=models.FusionQuery(
                fusion=models.Fusion.RRF
            ),

            limit=5,
            with_payload=True,
        )

        print("\nTOP 5 RESULTS\n")

        for rank, result in enumerate(
            response.points,
            start=1,
        ):

            payload = result.payload or {}

            print("=" * 100)

            print(
                f"RANK {rank} | "
                f"SCORE {result.score:.4f}"
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
