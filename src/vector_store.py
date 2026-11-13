from __future__ import annotations

from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)


VECTOR_SIZE = 384


class DenseVectorStore:

    def __init__(
        self,
        path: str | Path = "qdrant_data",
        collection_name: str = "lendlens_dense_v1",
    ):

        self.path = str(path)

        self.collection_name = collection_name

        self.client = QdrantClient(
            path=self.path
        )

    def reset_collection(self):

        if self.client.collection_exists(
            self.collection_name
        ):
            self.client.delete_collection(
                self.collection_name
            )

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )

    def upload_batch(
        self,
        ids: list[int],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
    ):

        points = [
            PointStruct(
                id=point_id,
                vector=vector,
                payload=payload,
            )
            for point_id, vector, payload
            in zip(
                ids,
                vectors,
                payloads,
            )
        ]

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
    ):

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )

        return response.points

    def count(self) -> int:

        result = self.client.count(
            collection_name=self.collection_name,
            exact=True,
        )

        return result.count
