from __future__ import annotations

from src.embeddings import BGEEmbedder
from src.vector_store import DenseVectorStore


def main():

    embedder = BGEEmbedder()

    store = DenseVectorStore(
        path="qdrant_core_data",
        collection_name="lendlens_core_dense_v1",
    )

    print("=" * 100)
    print("LENDLENS — DENSE RETRIEVAL")
    print("=" * 100)

    print("\nIndexed chunks:", store.count())

    while True:

        query = input(
            "\nAsk a question (or type exit): "
        ).strip()

        if query.lower() in {"exit", "quit"}:
            break

        if not query:
            continue

        query_vector = embedder.embed_query(query)

        results = store.search(
            query_vector=query_vector,
            top_k=5,
        )

        print("\nTOP 5 RESULTS\n")

        for rank, result in enumerate(results, start=1):

            payload = result.payload or {}

            print("=" * 100)

            print(
                f"RANK {rank} | SCORE {result.score:.4f}"
            )

            print("TITLE:", payload.get("title"))
            print("PUBLISHER:", payload.get("publisher"))
            print("AUTHORITY:", payload.get("authority"))
            print("CATEGORY:", payload.get("category"))
            print("TEMPORAL:", payload.get("temporal_role"))
            print("PAGE:", payload.get("page_number"))

            print("\nTEXT:\n")

            print(
                payload.get("text", "")[:1400]
            )

            print()


if __name__ == "__main__":
    main()
