from __future__ import annotations

from qdrant_client import (
    QdrantClient,
    models,
)

from src.embeddings import BGEEmbedder
from src.sparse_embeddings import BM25Embedder
from src.query_router import route_query
from src.reranker import CrossEncoderReranker


COLLECTION = "lendlens_core_dense_v1"


def main():

    client = QdrantClient(
        path="qdrant_core_data"
    )

    dense = BGEEmbedder()
    sparse = BM25Embedder()

    reranker = CrossEncoderReranker(
        model_name="Xenova/ms-marco-MiniLM-L-6-v2"
    )

    print("=" * 100)
    print("LENDLENS — ROUTED HYBRID + RERANKING")
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

        # --------------------------------------------------
        # STAGE 1:
        # Retrieve a reasonably broad shortlist.
        # --------------------------------------------------

        response = client.query_points(
            collection_name=COLLECTION,

            prefetch=[
                models.Prefetch(
                    query=dense_vector,
                    filter=routing.query_filter,
                    limit=40,
                ),

                models.Prefetch(
                    query=sparse_vector,
                    using="bm25",
                    filter=routing.query_filter,
                    limit=40,
                ),
            ],

            query=models.FusionQuery(
                fusion=models.Fusion.RRF
            ),

            limit=20,
            with_payload=True,
        )

        candidates = response.points

        if not candidates:

            print("\nNo evidence found.")
            continue

        texts = [
            (point.payload or {}).get(
                "text",
                "",
            )
            for point in candidates
        ]

        # --------------------------------------------------
        # STAGE 2:
        # Cross-encoder reranking.
        # --------------------------------------------------

        rerank_scores = reranker.rerank(
            query,
            texts,
        )

        ranked = list(
            zip(
                candidates,
                rerank_scores,
            )
        )

        ranked.sort(
            key=lambda x: x[1],
            reverse=True,
        )

        print("\nTOP 5 RERANKED RESULTS\n")

        for rank, (
            result,
            rerank_score,
        ) in enumerate(
            ranked[:5],
            start=1,
        ):

            payload = result.payload or {}

            print("=" * 100)

            print(
                f"RANK {rank}"
                f" | RERANK {rerank_score:.4f}"
                f" | HYBRID {result.score:.4f}"
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
