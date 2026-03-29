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
            """
        )


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
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM articles
            WHERE published >= ?
            ORDER BY published DESC
            LIMIT ?
            """,
            (cutoff_iso, limit),
        ).fetchall()
        return [dict(row) for row in rows]


def save_summary(window: str, content_md: str, html: str, source_count: int) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO summaries (window, created_at, content_md, html, source_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (window, datetime.now(timezone.utc).isoformat(), content_md, html, source_count),
        )
