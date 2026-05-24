"""Whisper transcription helper.

Accepts raw audio bytes (any format Whisper accepts: webm, mp4, mp3, wav)
and returns a transcript string.

Cost: $0.006 per minute of audio (whisper-1 model).

The OpenAI client is module-level lazy so we don't pay TCP+TLS handshake
per request.
"""
from __future__ import annotations

import io
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_WHISPER_MODEL = "whisper-1"

_CLIENT: Any = None


def _client():
    """Lazy module-level OpenAI client."""
    global _CLIENT
    if _CLIENT is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package not installed.") from exc
        _CLIENT = OpenAI(api_key=api_key)
    return _CLIENT


def transcribe_audio(
    audio_bytes: bytes,
    *,
    filename: str = "recording.webm",
    language: str | None = None,
) -> str:
    """Transcribe audio bytes using OpenAI Whisper API.

    Returns:
        Transcript string. Empty string if audio is silent/unintelligible.

    Raises:
        RuntimeError: If OPENAI_API_KEY is not set or API call fails.
    """
    client = _client()

    logger.info(
        "transcribing %.1f KB audio via Whisper (model=%s, language=%s)",
        len(audio_bytes) / 1024,
        _WHISPER_MODEL,
        language or "auto",
    )

    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename  # OpenAI SDK reads .name for content-type

    kwargs: dict = {
        "model": _WHISPER_MODEL,
        "file": audio_file,
        "response_format": "text",
    }
    if language:
        kwargs["language"] = language

    response = client.audio.transcriptions.create(**kwargs)
    transcript = str(response).strip()
    logger.info("transcript length: %d chars", len(transcript))
    return transcript


def detect_language_hint(transcript: str) -> str | None:
    """Heuristic: if >30% of chars are CJK, return 'zh'."""
    if not transcript:
        return None
    cjk_count = sum(
        1 for ch in transcript
        if "一" <= ch <= "鿿"
        or "㐀" <= ch <= "䶿"
        or "豈" <= ch <= "﫿"
    )
    ratio = cjk_count / len(transcript)
    return "zh" if ratio > 0.30 else "en"
