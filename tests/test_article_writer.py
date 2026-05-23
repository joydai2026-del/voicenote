"""Tests for the article writer module.

Live tests (test_generate_article_*) call the real Claude API using
ANTHROPIC_API_KEY from the environment. They are marked `live` and skipped
if the key is absent.

Unit tests (test_strip_code_fence, test_language_detection) never call any API.

Run all:
  pytest tests/test_article_writer.py -v

Run only unit tests:
  pytest tests/test_article_writer.py -v -m "not live"
"""
from __future__ import annotations

import os
import pytest

# Mark for live tests only (applied per-test below, not module-wide)
requires_anthropic = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping live Claude tests",
)


SAMPLE_TRANSCRIPT = """
So I've been thinking a lot about AI agents lately, and I think there's a really
important shift happening that most people are missing. It's not about the models
getting smarter — it's about the infrastructure around them.

Like, three years ago, if you wanted an AI to do something useful, you'd prompt it
and get text back. That was it. But now we're seeing these agent frameworks where
the AI can actually take actions — it can browse the web, write code, call APIs,
send emails. The model is becoming less of a chat interface and more like a worker
you can assign tasks to.

And the implications of that are huge. For founders, this means you can build
products that do 80% of their own work. You describe the goal, the agent figures
out the steps. I've been experimenting with this in my own company — we use AI
agents to handle initial customer research, draft proposals, even monitor our
competitors.

But here's the thing nobody talks about: the bottleneck isn't the AI anymore.
It's the human approval layer. Every time an agent needs to do something
significant — send an email, make a purchase, commit code to production —
someone has to review it. And that's actually okay. That's by design. You want
a human in the loop for high-stakes decisions.

The companies that are going to win in the next five years are the ones that
figure out the right approval granularity. Too many approvals and you kill the
efficiency. Too few and you introduce unacceptable risk. Finding that sweet spot
is the real product challenge of the AI agent era.
"""


@requires_anthropic
def test_generate_article_returns_valid_shape():
    """Call Claude with a sample transcript and verify the response shape."""
    from backend.article_writer import generate_article

    result = generate_article(SAMPLE_TRANSCRIPT)

    # Shape assertions
    assert isinstance(result, dict), "result should be a dict"
    assert "title" in result, "missing 'title' key"
    assert "body_md" in result, "missing 'body_md' key"
    assert "sections" in result, "missing 'sections' key"
    assert "cost_usd" in result, "missing 'cost_usd' key"

    # Title constraints
    assert isinstance(result["title"], str), "title should be a string"
    assert len(result["title"]) > 0, "title should not be empty"
    assert len(result["title"]) <= 70, (
        f"title too long ({len(result['title'])} chars): {result['title']!r}"
    )

    # Body constraints
    assert isinstance(result["body_md"], str), "body_md should be a string"
    word_count = len(result["body_md"].split())
    assert word_count >= 100, f"body too short ({word_count} words)"

    # Sections constraints
    assert isinstance(result["sections"], list), "sections should be a list"
    assert len(result["sections"]) >= 1, "sections should have at least 1 item"
    for i, section in enumerate(result["sections"]):
        assert "h2" in section, f"sections[{i}] missing 'h2'"
        assert "summary" in section, f"sections[{i}] missing 'summary'"

    # Cost is a non-negative float
    assert isinstance(result["cost_usd"], float), "cost_usd should be a float"
    assert result["cost_usd"] >= 0, "cost_usd should be non-negative"

    # Log the result for human review
    print(f"\n--- Article output ---")
    print(f"title: {result['title']!r}")
    print(f"body_md (first 300 chars): {result['body_md'][:300]}")
    print(f"sections: {result['sections']}")
    print(f"cost_usd: ${result['cost_usd']:.4f}")
    print(f"word count: {word_count}")


@requires_anthropic
def test_generate_article_handles_short_transcript():
    """Very short transcript should still produce some article (not crash)."""
    from backend.article_writer import generate_article

    short_transcript = "I think AI is interesting and will change the world."
    result = generate_article(short_transcript)

    assert "title" in result
    assert "body_md" in result
    assert len(result["title"]) > 0


def test_strip_code_fence():
    """Unit test for the code-fence stripper (no API call)."""
    from backend.article_writer import _strip_code_fence

    # With fence
    fenced = '```json\n{"title": "test"}\n```'
    assert _strip_code_fence(fenced) == '{"title": "test"}'

    # Without fence
    plain = '{"title": "test"}'
    assert _strip_code_fence(plain) == plain

    # Generic fence
    generic = '```\n{"title": "test"}\n```'
    assert _strip_code_fence(generic) == '{"title": "test"}'


def test_language_detection():
    """Unit test for CJK language heuristic (no API call)."""
    from backend.transcribe import detect_language_hint

    english = "This is an English transcript about AI agents and their impact."
    assert detect_language_hint(english) == "en"

    chinese = "今天我想谈谈人工智能代理的发展。这是一个非常重要的话题，对我们的未来影响深远。让我来解释一下为什么。"
    assert detect_language_hint(chinese) == "zh"

    assert detect_language_hint("") is None
