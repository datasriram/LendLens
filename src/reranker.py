from __future__ import annotations

from fastembed.rerank.cross_encoder import TextCrossEncoder


DEFAULT_RERANKER = "Xenova/ms-marco-MiniLM-L-6-v2"


class CrossEncoderReranker:

    def __init__(
        self,
        model_name: str = DEFAULT_RERANKER,
    ):
        self.model_name = model_name

        self.model = TextCrossEncoder(
            model_name=model_name
        )

    def rerank(
        self,
        query: str,
        documents: list[str],
    ) -> list[float]:

        return [
            float(score)
            for score in self.model.rerank(
                query,
                documents,
            )
        ]
