from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from src.retrieval import LendLensRetriever, RetrievalResult
from src.generation import LendLensGenerator
import os
from src.generation_providers import GenerationResult, GroqProvider
from src.guardrails import check_query
from src.timings import TimingProfile, measure


@dataclass
class PreparedQuestion:
    question: str
    results: list[RetrievalResult]
    routing: dict
    timings: TimingProfile
    elapsed: float
    blocked_answer: str | None = None
    guardrail_reason: str | None = None


class LendLensService:

    def __init__(self):
        self.retriever = LendLensRetriever()
        provider = os.getenv(
            "LENDLENS_GENERATION_PROVIDER", "ollama"
        ).strip().lower()

        if provider == "groq":
            self.generator = LendLensGenerator(
                provider=GroqProvider()
            )
        elif provider == "ollama":
            self.generator = LendLensGenerator(
                model="qwen3:4b"
            )
        else:
            raise ValueError(
                f"Unsupported generation provider: {provider}"
            )

    def prepare(self, question: str) -> PreparedQuestion:
        timings = TimingProfile()
        with measure(timings, "guardrail"):
            guardrail = check_query(question)

        if guardrail.blocked:
            return PreparedQuestion(
                question, [], {}, timings, timings.elapsed(), guardrail.message, guardrail.reason
            )

        with measure(timings, "retrieval_total"):
            results, routing = self.retriever.retrieve(
                question, top_k=5, expand_context=True, timings=timings
            )
        return PreparedQuestion(question, results, routing, timings, timings.elapsed())

    def ask(self, question: str) -> dict[str, Any]:
        data, _ = self.answer_prepared(self.prepare(question), self.generator)
        return data

    def answer_prepared(
        self, prepared: PreparedQuestion, generator: LendLensGenerator
    ) -> tuple[dict[str, Any], GenerationResult | None]:
        question, results, routing = prepared.question, prepared.results, prepared.routing
        timings = prepared.timings.fork(prepared.elapsed)
        if prepared.blocked_answer is not None:
            elapsed = timings.finish()
            return {
                "question": question,
                "answer": prepared.blocked_answer,
                "abstained": True,
                "blocked": True,
                "guardrail_reason": prepared.guardrail_reason,
                "routing": {},
                "sources": [],
                "latency_seconds": elapsed,
                "timings": timings.as_dict(),
            }, None

        generation = generator.generate(question, results, timings=timings)
        answer = generation.answer

        with measure(timings, "post_processing"):
            abstained = answer.strip().startswith(
                "I do not have sufficient evidence"
            )

            sources = []

            if not abstained:

                cited_numbers = {
                    int(number)
                    for number in re.findall(
                        r"\[S(\d+)\]",
                        answer,
                    )
                }

                for index, result in enumerate(
                    results,
                    start=1,
                ):

                    if (
                        cited_numbers
                        and index not in cited_numbers
                    ):
                        continue

                    metadata = result.metadata

                    sources.append(
                        {
                            "id": f"S{index}",
                            "title": metadata.get(
                                "title"
                            ),
                            "publisher": metadata.get(
                                "publisher"
                            ),
                            "authority": metadata.get(
                                "authority"
                            ),
                            "category": metadata.get(
                                "category"
                            ),
                            "temporal_role": metadata.get(
                                "temporal_role"
                            ),
                            "page": metadata.get(
                                "page_number"
                            ),
                            "url": (
                                metadata.get(
                                    "source_url"
                                )
                                or metadata.get(
                                    "url"
                                )
                            ),
                            "rerank_score":
                                result.rerank_score,
                        }
                    )

        elapsed = timings.finish()

        return {
            "question": question,
            "answer": answer,
            "abstained": abstained,
            "blocked": False,
            "guardrail_reason": None,
            "routing": routing,
            "sources": sources,
            "latency_seconds": elapsed,
            "timings": timings.as_dict(),
        }, generation
