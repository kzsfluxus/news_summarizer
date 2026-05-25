from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from config import DB_PATH


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                lang TEXT NOT NULL,
                country TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT 'hirek',
                rss_url TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                lang TEXT NOT NULL,
                country TEXT,
                category TEXT,
                published TEXT,
                scraped_at TEXT NOT NULL,
                content TEXT NOT NULL,
                content_hu TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                mini_summary_hu TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published);
            CREATE INDEX IF NOT EXISTS idx_articles_hash ON articles(content_hash);

            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                window TEXT NOT NULL,
                created_at TEXT NOT NULL,
                content_md TEXT NOT NULL,
                html TEXT NOT NULL,
                source_count INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                stage TEXT NOT NULL DEFAULT 'idle',
                progress INTEGER NOT NULL DEFAULT 0,
                message TEXT NOT NULL DEFAULT '',
                html TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '',
                stats TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def sync_sources(feeds: list[dict]) -> None:
    """
    Szinkronizálja a feeds.yaml tartalmát a sources táblával.
    Új forrást beszúr, meglévőt (name alapján) frissít.
    """
    with get_conn() as conn:
        for feed in feeds:
            conn.execute(
                """
                INSERT INTO sources (name, lang, country, category, rss_url)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    lang     = excluded.lang,
                    country  = excluded.country,
                    category = excluded.category,
                    rss_url  = excluded.rss_url
                """,
                (
                    feed["name"],
                    feed["lang"],
                    feed.get("country", ""),
                    feed.get("category", "hirek"),
                    feed["rss"],
                ),
            )


def list_sources() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM sources ORDER BY name").fetchall()
        return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Articles
# ---------------------------------------------------------------------------

def article_exists(url: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM articles WHERE url = ? LIMIT 1", (url,)).fetchone()
        return row is not None


def hash_exists(content_hash: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM articles WHERE content_hash = ? LIMIT 1", (content_hash,)).fetchone()
        return row is not None


def save_article(item: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO articles (
                url, title, source, lang, country, category, published,
                scraped_at, content, content_hu, content_hash, mini_summary_hu
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["link"],
                item["title"],
                item["source"],
                item["lang"],
                item.get("country", ""),
                item.get("category", "hirek"),
                item.get("published", ""),
                datetime.now(timezone.utc).isoformat(),
                item["clean_text"],
                item["clean_text_hu"],
                item["content_hash"],
                item["mini_summary_hu"],
            ),
        )


def list_articles_since(cutoff_iso: str, limit: int = 200) -> list[dict]:
    """
    Visszaadja a cutoff_iso utáni cikkeket.
    A published mező ISO 8601 UTC string – az összehasonlítás string-szinten
    helyes, feltéve hogy minden bejegyzés egységesen UTC+00:00 offsettel
    van tárolva (ahogy a feed_service garantálja).
    Biztonsági célból a cutoff-ot is UTC isoformat-ra normalizáljuk.
    """
    try:
        dt = datetime.fromisoformat(cutoff_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        cutoff_normalized = dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        cutoff_normalized = cutoff_iso

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM articles
            WHERE published >= ?
            ORDER BY published DESC
            LIMIT ?
            """,
            (cutoff_normalized, limit),
        ).fetchall()
        return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

def save_summary(window: str, content_md: str, html: str, source_count: int) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO summaries (window, created_at, content_md, html, source_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (window, datetime.now(timezone.utc).isoformat(), content_md, html, source_count),
        )


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def upsert_job(job_id: str, stage: str, progress: int, message: str,
               html: str, error: str, stats: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO jobs (job_id, stage, progress, message, html, error, stats, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                stage      = excluded.stage,
                progress   = excluded.progress,
                message    = excluded.message,
                html       = excluded.html,
                error      = excluded.error,
                stats      = excluded.stats,
                updated_at = excluded.updated_at
            """,
            (job_id, stage, progress, message, html, error, stats, now, now),
        )


def get_job(job_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return dict(row) if row else None


def get_active_job() -> dict | None:
    """Visszaadja az éppen futó jobot (ha van)."""
    running_stages = ("idle_start", "rss", "scrape", "markdown", "ollama", "html")
    placeholders = ",".join("?" * len(running_stages))
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT * FROM jobs WHERE stage IN ({placeholders}) ORDER BY created_at DESC LIMIT 1",
            running_stages,
        ).fetchone()
        return dict(row) if row else None
