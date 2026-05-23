"""Claude-powered article writer.

Takes a raw spoken transcript and returns a structured, publish-ready article.
Uses claude-sonnet-4-6 (cost-effective for MVP; see HOW-DECISION.md §3).

Output JSON schema:
{
  "title": str (≤70 chars, hook-style),
  "body_md": str (markdown 600-1200 words, intro + 3 sections + conclusion),
  "sections": [{"h2": str, "summary": str}, ...],
  "cost_usd": float
}
"""
from __future__ import annotations

import json
import logging
import os
import re

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"

# Approximate token cost for sonnet-4-6 (2026 pricing):
# Input: $3.00 / 1M tokens = $0.000003/tok
# Output: $15.00 / 1M tokens = $0.000015/tok
_COST_PER_INPUT_TOKEN = 3.00 / 1_000_000
_COST_PER_OUTPUT_TOKEN = 15.00 / 1_000_000

SYSTEM_PROMPT = """\
You are a professional writer and editor. Given a raw spoken transcript, \
write a polished, publish-ready article.

Rules:
- Extract the main insight or argument from the speaker's words
- Write in the speaker's voice but with editorial polish
- Eliminate filler words, repetition, and verbal tics
- Structure: punchy intro paragraph, 3 substantive sections with H2 headers, conclusion
- Length: 600-1200 words
- Tone: confident, specific, concrete — no corporate filler
- If the transcript is in Chinese (>30% CJK chars), write the article in Chinese
- If the transcript is in English, write in English

Output ONLY valid JSON in this exact shape (no markdown wrapper, no extra keys):
{
  "title": "<hook-style headline ≤70 characters>",
  "body_md": "<full article in markdown, 600-1200 words>",
  "sections": [
    {"h2": "<section 1 heading>", "summary": "<1-sentence summary>"},
    {"h2": "<section 2 heading>", "summary": "<1-sentence summary>"},
    {"h2": "<section 3 heading>", "summary": "<1-sentence summary>"}
  ]
}

Do not include any text outside the JSON object."""

USER_PROMPT_TEMPLATE = """\
Here is the raw spoken transcript to transform into a publish-ready article:

---
{transcript}
---

Write the article now. Return ONLY the JSON object."""


def generate_article(transcript: str) -> dict:
    """Transform a transcript into a structured article using Claude.

    Args:
        transcript: Raw spoken text from Whisper transcription.

    Returns:
        Dict with keys: title, body_md, sections, cost_usd.

    Raises:
        RuntimeError: If ANTHROPIC_API_KEY is not set or Claude API fails.
        ValueError: If Claude returns malformed JSON.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Export it or add to .env file."
        )

    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError(
            "anthropic package not installed. Run: pip install anthropic"
        ) from exc

    client = anthropic.Anthropic(api_key=api_key)

    user_message = USER_PROMPT_TEMPLATE.format(transcript=transcript.strip())

    logger.info(
        "generating article via Claude (model=%s, transcript_len=%d)",
        _MODEL,
        len(transcript),
    )

    response = client.messages.create(
        model=_MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = response.content[0].text.strip()
    logger.info("Claude response length: %d chars", len(raw_text))

    # Strip markdown code fences if Claude wraps in ```json ... ```
    raw_text = _strip_code_fence(raw_text)

    try:
        article = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.error("Claude returned non-JSON: %s", raw_text[:500])
        raise ValueError(
            f"Claude returned invalid JSON: {exc}. Raw: {raw_text[:200]}"
        ) from exc

    # Validate required keys
    required_keys = {"title", "body_md", "sections"}
    missing = required_keys - set(article.keys())
    if missing:
        raise ValueError(
            f"Claude response missing required keys: {missing}. Got: {list(article.keys())}"
        )

    # Calculate cost
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost_usd = (
        input_tokens * _COST_PER_INPUT_TOKEN
        + output_tokens * _COST_PER_OUTPUT_TOKEN
    )

    article["cost_usd"] = round(cost_usd, 6)

    logger.info(
        "article generated: title=%r, body_len=%d, cost=$%.4f",
        article.get("title", "")[:40],
        len(article.get("body_md", "")),
        cost_usd,
    )

    return article


def _strip_code_fence(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers if present."""
    pattern = r"^```(?:json)?\s*\n?(.*?)\n?```\s*$"
    match = re.match(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text
