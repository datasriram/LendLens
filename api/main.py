from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.service import LendLensService


service: LendLensService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):

    global service

    print("Loading LendLens models...")

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
def ask(request: AskRequest):

    if service is None:

        raise HTTPException(
            status_code=503,
            detail="LendLens is still loading.",
        )

    try:

        return service.ask(
            request.question
        )

    except Exception as exc:

        logging.exception("LendLens request failed")

        raise HTTPException(
            status_code=500,
            detail="Unable to process the request.",
        ) from exc
