"""VoiceNote FastAPI backend.

Endpoints:
  GET  /healthz                    — health check
  POST /articles/generate          — multipart audio → article JSON
  GET  /articles/{id}              — fetch saved article

Usage (local dev):
  uvicorn backend.main:app --reload --port 8000

Usage (Modal):
  modal serve backend/modal_app.py
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .article_writer import generate_article
from .storage import get_article, save_article
from .transcribe import transcribe_audio

logging.basicConfig(level=os.environ.get("VOICENOTE_LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# Maximum audio upload: 25 MB (Whisper API limit)
_MAX_AUDIO_BYTES = 25 * 1024 * 1024

# Allow all origins in dev; in prod set VOICENOTE_ALLOWED_ORIGINS
_ALLOWED_ORIGINS = os.environ.get(
    "VOICENOTE_ALLOWED_ORIGINS", "*"
).split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("VoiceNote backend starting up")
    yield
    logger.info("VoiceNote backend shutting down")


app = FastAPI(
    title="VoiceNote API",
    version="0.1.0",
    description="Talk for 5 minutes, get a publish-ready article.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Simple liveness probe. Returns 200 if the service is up."""
    return {"status": "ok", "version": "0.1.0"}


# ---------------------------------------------------------------------------
# Article generation
# ---------------------------------------------------------------------------


@app.post("/articles/generate")
async def generate(
    audio: UploadFile = File(..., description="Audio recording (webm, mp4, mp3, wav)"),
    user_id: str | None = None,
) -> JSONResponse:
    """Transcribe audio and generate a publish-ready article.

    Multipart form fields:
      - audio: audio file (required)
      - user_id: optional user identifier for storage

    Returns JSON:
    {
      "id": "<uuid>",
      "title": "<article title>",
      "body_md": "<full markdown article>",
      "sections": [{"h2": "...", "summary": "..."}, ...],
      "transcript": "<raw transcript>",
      "cost_usd": 0.036
    }
    """
    # Read and validate audio
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Audio file is empty.")
    if len(audio_bytes) > _MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Audio file too large. Max {_MAX_AUDIO_BYTES // 1024 // 1024} MB.",
        )

    filename = audio.filename or "recording.webm"
    logger.info(
        "generate request: filename=%s size=%.1f KB user=%s",
        filename,
        len(audio_bytes) / 1024,
        user_id or "anonymous",
    )

    # Step 1: Transcribe
    try:
        transcript = transcribe_audio(audio_bytes, filename=filename)
    except RuntimeError as exc:
        logger.error("transcription failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"Transcription failed: {exc}")

    if not transcript.strip():
        raise HTTPException(
            status_code=422,
            detail="Could not detect speech in the audio. Please try again with a clearer recording.",
        )

    logger.info("transcript: %d chars, snippet: %r", len(transcript), transcript[:80])

    # Step 2: Generate article
    try:
        article = generate_article(transcript)
    except RuntimeError as exc:
        logger.error("article generation failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"Article generation failed: {exc}")
    except ValueError as exc:
        logger.error("article generation returned invalid data: %s", exc)
        raise HTTPException(status_code=502, detail=f"Article writer returned invalid data: {exc}")

    # Step 3: Persist
    try:
        article_id = save_article(
            transcript=transcript,
            title=article["title"],
            article_md=article["body_md"],
            cost_usd=article.get("cost_usd", 0.0),
            user_id=user_id,
        )
    except Exception as exc:
        logger.warning("storage failed (non-fatal): %s", exc)
        # Non-fatal: return the article even if storage fails
        article_id = "unsaved"

    return JSONResponse(
        content={
            "id": article_id,
            "title": article["title"],
            "body_md": article["body_md"],
            "sections": article.get("sections", []),
            "transcript": transcript,
            "cost_usd": article.get("cost_usd", 0.0),
        }
    )


# ---------------------------------------------------------------------------
# Article retrieval
# ---------------------------------------------------------------------------


@app.get("/articles/{article_id}")
async def get_article_by_id(article_id: str) -> Any:
    """Fetch a previously generated article by ID."""
    if article_id == "unsaved":
        raise HTTPException(status_code=404, detail="Article was not persisted.")

    record = get_article(article_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Article not found.")

    return record
