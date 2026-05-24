"""VoiceNote FastAPI backend.

Endpoints:
  GET  /healthz                    health check
  POST /articles/generate          multipart audio -> article JSON (auth + rate limit)
  GET  /articles/{id}              fetch saved article (auth)
"""
from __future__ import annotations

import hmac
import logging
import os
import time
from collections import OrderedDict, deque
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .article_writer import generate_article
from .storage import get_article, save_article
from .transcribe import transcribe_audio

logging.basicConfig(level=os.environ.get("VOICENOTE_LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

API_KEY = os.environ.get("VOICENOTE_API_KEY", "").strip()

# 25 MB is the Whisper API limit; we keep that as the backend cap. The Next.js
# proxy caps tighter (default 4 MB) to fit Vercel Hobby; advanced users hitting
# the backend directly with the API key can push up to 25 MB.
_MAX_AUDIO_BYTES = int(os.environ.get("VOICENOTE_MAX_AUDIO_BYTES", 25 * 1024 * 1024))

# Per-IP rate limit (default 5/hour). Each request hits Whisper (~$0.03 for 5 min)
# + Claude (~$0.04), so the budget impact per accepted request is ~$0.07. Keep
# the limit conservative for V0.1.
RATE_LIMIT_PER_HOUR = int(os.environ.get("RATE_LIMIT_PER_HOUR", 5))
_MAX_RATE_LIMIT_BUCKETS = int(os.environ.get("MAX_RATE_LIMIT_BUCKETS", 5_000))
_request_log: OrderedDict[str, deque[float]] = OrderedDict()

TRUSTED_PROXIES = {
    ip.strip() for ip in os.environ.get("TRUSTED_PROXIES", "").split(",") if ip.strip()
}

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "VOICENOTE_ALLOWED_ORIGINS", "http://localhost:3000"
    ).split(",")
    if origin.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("VoiceNote backend starting up")
    yield
    logger.info("VoiceNote backend shutting down")


class BodySizeLimitMiddleware:
    """Reject oversized POST bodies BEFORE FastAPI parses the multipart upload.

    Strategy: drain the body in middleware (chunk-by-chunk, bounded by max_bytes),
    then replay it to the downstream app via a new receive callable. If the cap
    is exceeded mid-read we short-circuit with 413 and the app never sees the
    body at all. This is the only way to beat Starlette's multipart parser to
    the response: raising an exception from inside receive() gets caught by the
    parser and turned into a generic 400, hiding the real reason.

    Memory cost: 2x peak body size during the replay window (middleware buffer +
    eventual UploadFile spool). The cap is small enough (25 MB) that this is
    well within the Modal container's 1 GB allocation.
    """

    def __init__(self, app, max_bytes: int, paths: tuple[str, ...] = ("/articles/generate",)):
        self.app = app
        self.max_bytes = max_bytes
        self.paths = paths

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "POST" or scope.get("path") not in self.paths:
            return await self.app(scope, receive, send)

        # Cheap fast-path: reject on honest Content-Length before reading any body.
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value.decode("ascii"))
                except (ValueError, UnicodeDecodeError):
                    declared = 0
                if declared > self.max_bytes:
                    await self._send_413(send)
                    return
                break

        # Drain the body with a hard byte cap.
        total = 0
        chunks: list[bytes] = []
        more_body = True
        while more_body:
            message = await receive()
            mtype = message["type"]
            if mtype == "http.disconnect":
                return
            if mtype != "http.request":
                continue
            body = message.get("body", b"")
            total += len(body)
            if total > self.max_bytes:
                await self._send_413(send)
                return
            chunks.append(body)
            more_body = message.get("more_body", False)

        # Replay the drained body to the downstream app.
        replay_iter = iter(chunks)
        replay_done = False

        async def replay_receive():
            nonlocal replay_done
            try:
                chunk = next(replay_iter)
            except StopIteration:
                if replay_done:
                    return {"type": "http.disconnect"}
                replay_done = True
                return {"type": "http.request", "body": b"", "more_body": False}
            return {"type": "http.request", "body": chunk, "more_body": True}

        await self.app(scope, replay_receive, send)

    async def _send_413(self, send):
        body = b'{"detail":"Request body too large"}'
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


app = FastAPI(
    title="VoiceNote API",
    version="0.1.2",
    description="Talk for 5 minutes, get a publish-ready article.",
    lifespan=lifespan,
)

app.add_middleware(BodySizeLimitMiddleware, max_bytes=_MAX_AUDIO_BYTES)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)


# Auth + rate limit

def _client_ip(request: Request) -> str:
    direct = request.client.host if request.client else "unknown"
    if TRUSTED_PROXIES and direct in TRUSTED_PROXIES:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip() or direct
    return direct


def _enforce_rate_limit(ip: str) -> None:
    now = time.time()
    window_start = now - 3600
    bucket = _request_log.get(ip)
    if bucket is None:
        bucket = deque()
        _request_log[ip] = bucket
        while len(_request_log) > _MAX_RATE_LIMIT_BUCKETS:
            _request_log.popitem(last=False)
    else:
        _request_log.move_to_end(ip)
    while bucket and bucket[0] < window_start:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {RATE_LIMIT_PER_HOUR}/hour per IP",
        )
    bucket.append(now)


def _require_api_key(presented: str | None) -> None:
    if not API_KEY:
        raise HTTPException(
            status_code=503,
            detail="VOICENOTE_API_KEY is not configured on the server",
        )
    if not presented or not hmac.compare_digest(API_KEY, presented):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


# Routes

@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.1"}


@app.post("/articles/generate")
async def generate(
    request: Request,
    audio: UploadFile = File(..., description="Audio recording (webm, mp4, mp3, wav)"),
    user_id: str | None = None,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> JSONResponse:
    """Transcribe audio and generate a publish-ready article."""
    _require_api_key(x_api_key)
    _enforce_rate_limit(_client_ip(request))

    # Cheap pre-check: reject obviously oversized uploads via Content-Length
    # BEFORE we buffer anything. UploadFile would otherwise let us hold the
    # entire payload in memory before any size check.
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared = int(content_length)
        except ValueError:
            declared = 0
        if declared > _MAX_AUDIO_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Audio file too large. Max {_MAX_AUDIO_BYTES // 1024 // 1024} MB.",
            )

    # Stream-read the multipart audio with a hard byte cap so a lying or absent
    # Content-Length cannot make us buffer unbounded data.
    audio_bytes = bytearray()
    chunk_size = 64 * 1024
    while True:
        chunk = await audio.read(chunk_size)
        if not chunk:
            break
        audio_bytes.extend(chunk)
        if len(audio_bytes) > _MAX_AUDIO_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Audio file too large. Max {_MAX_AUDIO_BYTES // 1024 // 1024} MB.",
            )
    audio_bytes = bytes(audio_bytes)
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Audio file is empty.")

    filename = audio.filename or "recording.webm"
    logger.info(
        "generate request: filename=%s size=%.1f KB",
        filename,
        len(audio_bytes) / 1024,
    )

    # Step 1: Transcribe
    try:
        transcript = transcribe_audio(audio_bytes, filename=filename)
    except RuntimeError as exc:
        logger.error("transcription failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"Transcription failed: {exc}") from exc

    if not transcript.strip():
        raise HTTPException(
            status_code=422,
            detail="Could not detect speech in the audio. Please try again with a clearer recording.",
        )

    logger.info("transcript: %d chars", len(transcript))

    # Step 2: Generate article
    try:
        article = generate_article(transcript)
    except RuntimeError as exc:
        logger.error("article generation failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"Article generation failed: {exc}") from exc
    except ValueError as exc:
        logger.error("article writer returned invalid data: %s", exc)
        raise HTTPException(status_code=502, detail="Article writer returned malformed output") from exc

    # Step 3: Persist (non-fatal)
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


@app.get("/articles/{article_id}")
async def get_article_by_id(
    article_id: str,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> Any:
    _require_api_key(x_api_key)
    if article_id == "unsaved":
        raise HTTPException(status_code=404, detail="Article was not persisted.")
    record = get_article(article_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Article not found.")
    return record
