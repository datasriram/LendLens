from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Protocol

import ollama
import requests
from groq import Groq


@dataclass
class Completion:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None


@dataclass
class GenerationResult:
    answer: str
    evidence_status: str
    citations: list[str]
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    generation_latency_seconds: float | None = None
    estimated_cost_usd: float | None = None
    citation_ids_valid: bool | None = None


class Provider(Protocol):
    name: str
    model: str

    def complete(self, system: str, prompt: str, schema: dict) -> Completion: ...


class ProviderError(RuntimeError):
    pass


def post_json(url: str, headers: dict, body: dict, provider: str) -> dict:
    try:
        response = requests.post(
            url, headers=headers, json=body, timeout=180, allow_redirects=False
        )
    except requests.RequestException as exc:
        raise ProviderError(f"{provider}: {type(exc).__name__}") from None
    if response.status_code != 200:
        raise ProviderError(f"{provider}: HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError:
        raise ProviderError(f"{provider}: invalid JSON response") from None


def estimate_cost(
    input_tokens: int | None, output_tokens: int | None, rates: tuple[float, float]
) -> float | None:
    if input_tokens is None or output_tokens is None:
        return None
    return round((input_tokens * rates[0] + output_tokens * rates[1]) / 1_000_000, 9)


@dataclass
class OllamaProvider:
    model: str = "qwen3:4b"
    name = "ollama"

    def complete(self, system: str, prompt: str, schema: dict) -> Completion:
        response = ollama.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            think=False,
            format=schema,
            keep_alive="30m",
            options={"temperature": 0, "num_predict": 384, "num_ctx": 4096},
        )
        return Completion(
            response["message"]["content"],
            response.get("prompt_eval_count"),
            response.get("eval_count"),
            0.0,
        )


@dataclass
class OpenAIProvider:
    model: str
    name = "openai"
    key_env = "OPENAI_API_KEY"

    def complete(self, system: str, prompt: str, schema: dict) -> Completion:
        key = os.getenv(self.key_env)
        if not key:
            raise ProviderError(f"Missing {self.key_env}")
        data = post_json(
            "https://api.openai.com/v1/responses",
            {"Authorization": f"Bearer {key}"},
            {
                "model": self.model, "instructions": system, "input": prompt,
                "store": False, "reasoning": {"effort": "none"}, "temperature": 0,
                "max_output_tokens": 220,
                "text": {"format": {
                    "type": "json_schema", "name": "lendlens_answer", "strict": True,
                    "schema": {**schema, "additionalProperties": False},
                }},
            },
            self.name,
        )
        text = "".join(
            part["text"]
            for item in data.get("output", []) if item.get("type") == "message"
            for part in item.get("content", []) if part.get("type") == "output_text"
        )
        usage = data.get("usage") or {}
        inputs, outputs = usage.get("input_tokens"), usage.get("output_tokens")
        # Standard uncached text rates per million tokens, OpenAI model catalog.
        rates = (0.1, 0.5) if self.model == "gpt-6-luna" else (1.0, 5.0)
        return Completion(text, inputs, outputs, estimate_cost(inputs, outputs, rates))


@dataclass
class GeminiProvider:
    model: str = "gemini-3.8-flash"
    name = "gemini"
    key_env = "GEMINI_API_KEY"

    def complete(self, system: str, prompt: str, schema: dict) -> Completion:
        key = os.getenv(self.key_env)
        if not key:
            raise ProviderError(f"Missing {self.key_env}")
        data = post_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            {"x-goog-api-key": key},
            {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0, "maxOutputTokens": 512,
                    "thinkingConfig": {"thinkingLevel": "low", "includeThoughts": False},
                    "responseMimeType": "application/json", "responseJsonSchema": schema,
                },
            },
            self.name,
        )
        candidates = data.get("candidates") or []
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
        usage = data.get("usageMetadata") or {}
        inputs = usage.get("promptTokenCount")
        outputs = usage.get("candidatesTokenCount")
        billed_outputs = (
            (outputs or 0) + usage.get("thoughtsTokenCount", 0) if usage else None
        )
        # Google standard paid-tier rates. Introductory pricing expires in 2026.
        rates = (0.75, 3.75) if date.today() < date(2027, 1, 1) else (1.50, 7.50)
        return Completion(text, inputs, outputs, estimate_cost(inputs, billed_outputs, rates))




@dataclass
class GroqProvider:
    model: str = "qwen/qwen3.8-27b"
    name = "groq"
    key_env = "GROQ_API_KEY"

    def complete(self, system: str, prompt: str, schema: dict) -> Completion:
        key = os.getenv(self.key_env)

        if not key:
            raise ProviderError(f"Missing {self.key_env}")

        client = Groq(api_key=key)

        strict_schema = {
            **schema,
            "additionalProperties": False,
        }

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_completion_tokens=768,
                reasoning_effort="none",
                response_format={
                    "type": "json_object",
                },
            )
        except Exception as exc:
            raise ProviderError(
                f"{self.name}: {type(exc).__name__}: {exc}"
            ) from None

        usage = getattr(response, "usage", None)

        input_tokens = (
            getattr(usage, "prompt_tokens", None)
            if usage is not None
            else None
        )

        output_tokens = (
            getattr(usage, "completion_tokens", None)
            if usage is not None
            else None
        )

        return Completion(
            text=response.choices[0].message.content or "",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=0.0,
        )

