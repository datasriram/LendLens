from __future__ import annotations

from typing import Iterable

import numpy as np
from fastembed import TextEmbedding


DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


class BGEEmbedder:

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        batch_size: int = 64,
    ):
        self.model_name = model_name
        self.batch_size = batch_size

        self.model = TextEmbedding(
            model_name=model_name
        )

    def embed_documents(
        self,
        texts: Iterable[str],
    ) -> list[list[float]]:

        texts = list(texts)

        embeddings = self.model.embed(
            texts,
            batch_size=self.batch_size,
        )

        return [
            vector.tolist()
            for vector in embeddings
        ]

    def embed_query(
        self,
        query: str,
    ) -> list[float]:

        vector = next(
            self.model.query_embed(query)
        )

        return vector.tolist()


def cosine_similarity(
    a: list[float],
    b: list[float],
) -> float:

    a_np = np.asarray(a)
    b_np = np.asarray(b)

    denominator = (
        np.linalg.norm(a_np)
        * np.linalg.norm(b_np)
    )

    if denominator == 0:
        return 0.0

    return float(
        np.dot(a_np, b_np) / denominator
    )

