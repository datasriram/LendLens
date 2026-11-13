from __future__ import annotations

from fastembed import SparseTextEmbedding
from qdrant_client.models import SparseVector


class BM25Embedder:

    def __init__(
        self,
        model_name: str = "Qdrant/bm25",
        batch_size: int = 256,
    ):
        self.model_name = model_name
        self.batch_size = batch_size

        self.model = SparseTextEmbedding(
            model_name=model_name
        )

    def embed_documents(
        self,
        texts: list[str],
    ) -> list[SparseVector]:

        vectors = list(
            self.model.embed(
                texts,
                batch_size=self.batch_size,
            )
        )

        return [
            SparseVector(
                indices=v.indices.tolist(),
                values=v.values.tolist(),
            )
            for v in vectors
        ]

    def embed_query(
        self,
        text: str,
    ) -> SparseVector:

        vector = next(
            self.model.embed([text])
        )

        return SparseVector(
            indices=vector.indices.tolist(),
            values=vector.values.tolist(),
        )
