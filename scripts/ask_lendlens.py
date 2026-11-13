from __future__ import annotations

from src.retrieval import LendLensRetriever
from src.generation import LendLensGenerator


def print_sources(results):

    print("\n" + "=" * 100)
    print("SOURCES")
    print("=" * 100)

    for i, result in enumerate(
        results,
        start=1,
    ):

        m = result.metadata

        print(f"\n[S{i}] {m.get('title')}")

        print(
            "Publisher:",
            m.get("publisher"),
        )

        print(
            "Authority:",
            m.get("authority"),
        )

        print(
            "Temporal:",
            m.get("temporal_role"),
        )

        print(
            "Page:",
            m.get("page_number"),
        )

        url = (
            m.get("source_url")
            or m.get("url")
        )

        if url:
            print(
                "URL:",
                url,
            )


def main():

    print("=" * 100)
    print("LENDLENS")
    print("NBFC Regulatory & Policy Intelligence")
    print("=" * 100)

    print("\nLoading retrieval models...")

    retriever = LendLensRetriever()

    generator = LendLensGenerator(
        model="qwen3:4b"
    )

    print("Ready.")

    while True:

        question = input(
            "\nAsk LendLens (or type exit): "
        ).strip()

        if question.lower() in {
            "exit",
            "quit",
        }:
            break

        if not question:
            continue

        results, routing = retriever.retrieve(
            question,
            top_k=5,
        )

        print("\nRouting:")
        print(routing)

        print("\nGenerating grounded answer...\n")

        answer = generator.answer(
            question,
            results,
        )

        print("=" * 100)
        print("ANSWER")
        print("=" * 100)

        print(answer)

        print_sources(results)


if __name__ == "__main__":
    main()
