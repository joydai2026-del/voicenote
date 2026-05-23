"""Article draft storage.

Strategy: try Supabase first (if SUPABASE_URL + SUPABASE_ANON_KEY are set),
fall back to SQLite in /tmp/voicenote.db.

Supabase schema (create once in Supabase dashboard):
    create table articles (
        id uuid primary key default gen_random_uuid(),
        user_id text,
        transcript text,
        article_md text,
        title text,
        status text default 'complete',
        cost_usd float,
        created_at timestamptz default now()
    );
"""
from __future__ import annotations

import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_SQLITE_PATH = os.environ.get("VOICENOTE_DB_PATH", "/tmp/voicenote.db")


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def save_article(
    *,
    transcript: str,
    title: str,
    article_md: str,
    cost_usd: float = 0.0,
    user_id: str | None = None,
    status: str = "complete",
) -> str:
    """Persist an article draft. Returns the article UUID."""
    article_id = str(uuid.uuid4())
    record = {
        "id": article_id,
        "user_id": user_id or "anonymous",
        "transcript": transcript,
        "title": title,
        "article_md": article_md,
        "cost_usd": cost_usd,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if _supabase_configured():
        try:
            _supabase_upsert(record)
            logger.info("article %s saved to Supabase", article_id)
            return article_id
        except Exception as exc:
            logger.warning("Supabase save failed (%s), falling back to SQLite", exc)

    _sqlite_upsert(record)
    logger.info("article %s saved to SQLite (%s)", article_id, _SQLITE_PATH)
    return article_id


def get_article(article_id: str) -> dict[str, Any] | None:
    """Fetch an article by ID. Returns None if not found."""
    if _supabase_configured():
        try:
            return _supabase_get(article_id)
        except Exception as exc:
            logger.warning("Supabase get failed (%s), falling back to SQLite", exc)

    return _sqlite_get(article_id)


# ---------------------------------------------------------------------------
# Supabase path
# ---------------------------------------------------------------------------


def _supabase_configured() -> bool:
    return bool(
        os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_ANON_KEY")
    )


def _supabase_upsert(record: dict[str, Any]) -> None:
    try:
        from supabase import create_client  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "supabase package not installed. Run: pip install supabase"
        ) from exc

    client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_ANON_KEY"],
    )
    # Map our internal field names to Supabase column names
    row = {
        "id": record["id"],
        "user_id": record["user_id"],
        "transcript": record["transcript"],
        "title": record["title"],
        "article_md": record["article_md"],
        "status": record["status"],
        "created_at": record["created_at"],
    }
    client.table("articles").upsert(row).execute()


def _supabase_get(article_id: str) -> dict[str, Any] | None:
    try:
        from supabase import create_client
    except ImportError:
        return None

    client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_ANON_KEY"],
    )
    result = (
        client.table("articles")
        .select("*")
        .eq("id", article_id)
        .limit(1)
        .execute()
    )
    data = result.data
    if not data:
        return None
    row = data[0]
    return {
        "id": row["id"],
        "title": row.get("title", ""),
        "article_md": row.get("article_md", ""),
        "transcript": row.get("transcript", ""),
        "status": row.get("status", "complete"),
        "created_at": row.get("created_at", ""),
    }


# ---------------------------------------------------------------------------
# SQLite fallback
# ---------------------------------------------------------------------------


def _get_sqlite_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            transcript TEXT,
            title TEXT,
            article_md TEXT,
            cost_usd REAL DEFAULT 0,
            status TEXT DEFAULT 'complete',
            created_at TEXT
        )
    """)
    conn.commit()
    return conn


def _sqlite_upsert(record: dict[str, Any]) -> None:
    conn = _get_sqlite_conn()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO articles
                (id, user_id, transcript, title, article_md, cost_usd, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["user_id"],
                record["transcript"],
                record["title"],
                record["article_md"],
                record.get("cost_usd", 0.0),
                record["status"],
                record["created_at"],
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _sqlite_get(article_id: str) -> dict[str, Any] | None:
    conn = _get_sqlite_conn()
    try:
        row = conn.execute(
            "SELECT * FROM articles WHERE id = ?", (article_id,)
        ).fetchone()
        if row is None:
            return None
        return dict(row)
    finally:
        conn.close()
