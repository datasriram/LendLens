from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from qdrant_client import QdrantClient, models

from src.embeddings import BGEEmbedder
from src.sparse_embeddings import BM25Embedder
from src.query_router import route_query
from src.reranker import CrossEncoderReranker
from src.timings import TimingProfile, measure


COLLECTION = "lendlens_core_dense_v1"


@dataclass
class RetrievalResult:
    point_id: int
    text: str
    metadata: dict[str, Any]
    rerank_score: float
    hybrid_score: float
    context_expanded: bool = False


class LendLensRetriever:

    def __init__(self):

        qdrant_url = os.getenv("LENDLENS_QDRANT_URL", "").strip()

        if qdrant_url:
            qdrant_key = os.getenv("LENDLENS_QDRANT_API_KEY")
            self.client = QdrantClient(
                url=qdrant_url,
                api_key=qdrant_key or None,
                timeout=60,
            )
        else:
            self.client = QdrantClient(
                path="qdrant_core_data"
            )

        self.dense = BGEEmbedder()
        self.sparse = BM25Embedder()
        self.reranker = CrossEncoderReranker()

    def _same_document(
        self,
        a: dict[str, Any],
        b: dict[str, Any],
    ) -> bool:

        a_path = a.get("local_path")
        b_path = b.get("local_path")

        if a_path and b_path:
            return a_path == b_path

        a_source = a.get("source_id")
        b_source = b.get("source_id")

        if a_source and b_source:
            return a_source == b_source

        return (
            a.get("title") == b.get("title")
            and
            a.get("publisher") == b.get("publisher")
        )

    def _expand_neighbors(
        self,
        results: list[RetrievalResult],
        expand_top_n: int = 2,
    ) -> list[RetrievalResult]:

        final_results: list[RetrievalResult] = []

        seen_ids: set[int] = set()

        for index, result in enumerate(results):

            if result.point_id not in seen_ids:

                final_results.append(result)
                seen_ids.add(result.point_id)

            # Only expand the strongest few results.
            if index >= expand_top_n:
                continue

            neighbor_ids = []

            if result.point_id > 0:
                neighbor_ids.append(
                    result.point_id - 1
                )

            neighbor_ids.append(
                result.point_id + 1
            )

            records = self.client.retrieve(
                collection_name=COLLECTION,
                ids=neighbor_ids,
                with_payload=True,
                with_vectors=False,
            )

            records = sorted(
                records,
                key=lambda x: int(x.id),
            )

            for record in records:

                neighbor_metadata = (
                    record.payload or {}
                )

                # Prevent accidentally crossing into
                # another document.
                if not self._same_document(
                    result.metadata,
                    neighbor_metadata,
                ):
                    continue

                neighbor_id = int(record.id)

                if neighbor_id in seen_ids:
                    continue

                text = neighbor_metadata.get(
                    "text",
                    "",
                )

                if not text:
                    continue

                final_results.append(
                    RetrievalResult(
                        point_id=neighbor_id,
                        text=text,
                        metadata={
                            **neighbor_metadata,
                            "context_neighbor_of":
                                result.point_id,
                        },
                        rerank_score=
                            result.rerank_score,
                        hybrid_score=
                            result.hybrid_score,
                        context_expanded=True,
                    )
                )

                seen_ids.add(neighbor_id)

        return final_results

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        candidate_limit: int = 20,
        expand_context: bool = True,
        *,
        timings: TimingProfile | None = None,
    ) -> tuple[
        list[RetrievalResult],
        dict,
    ]:

        with measure(timings, "routing"):
            routing = route_query(query)

        with measure(timings, "dense_embedding"):
            dense_vector = (
                self.dense.embed_query(query)
            )

        with measure(timings, "sparse_embedding"):
            sparse_vector = (
                self.sparse.embed_query(query)
            )

        with measure(timings, "qdrant_retrieval"):
            response = self.client.query_points(
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

                limit=candidate_limit,

                with_payload=True,
            )

        candidates = response.points

        if not candidates:
            return [], routing.details

        with measure(timings, "reranking"):
            texts = [
                (point.payload or {}).get(
                    "text",
                    "",
                )
                for point in candidates
            ]

            rerank_scores = (
                self.reranker.rerank(
                    query,
                    texts,
                )
            )

            ranked = sorted(
                zip(
                    candidates,
                    rerank_scores,
                ),
                key=lambda x: x[1],
                reverse=True,
            )

            results = []

            for point, score in ranked[:top_k]:

                results.append(
                    RetrievalResult(
                        point_id=int(point.id),

                        text=(
                            point.payload or {}
                        ).get(
                            "text",
                            "",
                        ),

                        metadata=(
                            point.payload or {}
                        ),

                        rerank_score=float(
                            score
                        ),

                        hybrid_score=float(
                            point.score
                        ),

                        context_expanded=False,
                    )
                )

        if expand_context:
            with measure(timings, "context_expansion"):

                results = self._expand_neighbors(
                    results,
                    expand_top_n=2,
                )

        return results, routing.details
