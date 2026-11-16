from __future__ import annotations

from collections import deque
from contextlib import asynccontextmanager
from hmac import compare_digest
import logging
import os
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from src.retrieval import COLLECTION
from src.service import LendLensService


service: LendLensService | None = None
public_demo = os.getenv("LENDLENS_PUBLIC_DEMO") == "1"
demo_token = os.getenv("LENDLENS_DEMO_TOKEN", "")
demo_lock = Lock()
demo_starts: deque[float] = deque()
demo_active = False
DEMO_REQUESTS_PER_MINUTE = 12


def validate_demo_config() -> None:
    required = (
        "GROQ_API_KEY", "LENDLENS_QDRANT_URL",
        "LENDLENS_QDRANT_API_KEY", "LENDLENS_DEMO_TOKEN",
    )
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if missing:
        raise RuntimeError("Missing demo settings: " + ", ".join(missing))
    if len(demo_token) < 32:
        raise RuntimeError("LENDLENS_DEMO_TOKEN must be at least 32 characters")
    if os.getenv("LENDLENS_GENERATION_PROVIDER") != "groq":
        raise RuntimeError("The public demo requires the Groq provider")
    endpoint = urlsplit(os.environ["LENDLENS_QDRANT_URL"])
    if endpoint.scheme != "https" or not endpoint.hostname or endpoint.username:
        raise RuntimeError("LENDLENS_QDRANT_URL must be an HTTPS endpoint")


def admit_demo_request(authorization: str | None) -> None:
    global demo_active

    expected = f"Bearer {demo_token}".encode("utf-8")
    if not compare_digest((authorization or "").encode("utf-8"), expected):
        raise HTTPException(401, "Unauthorized", headers={"WWW-Authenticate": "Bearer"})

    with demo_lock:
        now = monotonic()
        while demo_starts and now - demo_starts[0] >= 60:
            demo_starts.popleft()
        if len(demo_starts) >= DEMO_REQUESTS_PER_MINUTE:
            retry_after = max(1, int(60 - (now - demo_starts[0])) + 1)
            raise HTTPException(429, "Demo rate limit reached", headers={"Retry-After": str(retry_after)})
        if demo_active:
            raise HTTPException(429, "Demo is busy", headers={"Retry-After": "5"})
        demo_starts.append(now)
        demo_active = True


@asynccontextmanager
async def lifespan(app: FastAPI):

    global service

    if public_demo:
        validate_demo_config()

    print("Loading LendLens models...")

    if public_demo:
        try:
            configured_service = LendLensService()
            if not configured_service.retriever.client.collection_exists(COLLECTION):
                raise RuntimeError("Expected collection is missing")
        except Exception as exc:
            raise RuntimeError(
                f"Demo startup could not initialize models or verify Qdrant ({type(exc).__name__})"
            ) from None
        service = configured_service
    else:
        service = LendLensService()

    print("LendLens ready.")

    yield


app = FastAPI(
    title="LendLens API",
    description=(
        "Evidence-grounded NBFC regulatory "
        "and policy intelligence API."
    ),
    version="0.1.0",
    docs_url=None if public_demo else "/docs",
    redoc_url=None if public_demo else "/redoc",
    openapi_url=None if public_demo else "/openapi.json",
    lifespan=lifespan,
)


class AskRequest(BaseModel):

    question: str = Field(
        min_length=3,
        max_length=1000,
    )


@app.get("/health")
def health():

    return {
        "status": "ok",
        "service": "LendLens",
        "models_loaded": (
            service is not None
        ),
    }


@app.post("/ask")
def ask(request: AskRequest, authorization: str | None = Header(default=None)):
    global demo_active

    if service is None:

        raise HTTPException(
            status_code=503,
            detail="LendLens is still loading.",
        )

    if public_demo:
        admit_demo_request(authorization)

    try:
        result = service.ask(request.question)
        if public_demo:
            for field in ("routing", "timings", "guardrail_reason"):
                result.pop(field, None)
            for source in result.get("sources", []):
                source.pop("rerank_score", None)
        return result
    except Exception as exc:
        if public_demo:
            logging.error("LendLens request failed (%s)", type(exc).__name__)
        else:
            logging.exception("LendLens request failed")
        raise HTTPException(500, "Unable to process the request.") from None
    finally:
        if public_demo:
            with demo_lock:
                demo_active = False
