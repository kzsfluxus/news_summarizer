"""
Adatbázis-réteg – SQLite.

Táblák:
  sources          – RSS források (feeds.yaml tükre)
  articles         – Feldolgozott cikkek + relevance_score
  article_keywords – KeyBERT kulcsszavak
  article_entities – GLiNER entitások
  topics           – TF-IDF klaszterek (3. fázis)
  article_topics   – Cikk–téma kapcsolatok (3. fázis)
  summaries        – Időablakos Ollama összefoglalók
  jobs             – Pipeline job állapotok

Minden dátum ISO 8601 UTC stringként tárolódik.
"""

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
                mini_summary_hu TEXT NOT NULL,
                relevance_score REAL NOT NULL DEFAULT 0.0
            );

            CREATE INDEX IF NOT EXISTS idx_articles_published  ON articles(published);
            CREATE INDEX IF NOT EXISTS idx_articles_hash       ON articles(content_hash);
            CREATE INDEX IF NOT EXISTS idx_articles_relevance  ON articles(relevance_score DESC);

            CREATE TABLE IF NOT EXISTS article_keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
                keyword TEXT NOT NULL,
                score REAL NOT NULL DEFAULT 0.0,
                UNIQUE(article_id, keyword)
            );

            CREATE INDEX IF NOT EXISTS idx_keywords_article ON article_keywords(article_id);
            CREATE INDEX IF NOT EXISTS idx_keywords_text    ON article_keywords(keyword);

            CREATE TABLE IF NOT EXISTS article_entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
                entity_text TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                score REAL NOT NULL DEFAULT 0.0,
                UNIQUE(article_id, entity_text, entity_type)
            );

            CREATE INDEX IF NOT EXISTS idx_entities_article ON article_entities(article_id);
            CREATE INDEX IF NOT EXISTS idx_entities_type    ON article_entities(entity_type);
            CREATE INDEX IF NOT EXISTS idx_entities_text    ON article_entities(entity_text);

            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                window TEXT NOT NULL,
                created_at TEXT NOT NULL,
                label TEXT NOT NULL,
                keywords TEXT NOT NULL,
                article_count INTEGER NOT NULL DEFAULT 0,
                trend_score REAL NOT NULL DEFAULT 0.0
            );

            CREATE INDEX IF NOT EXISTS idx_topics_window  ON topics(window);
            CREATE INDEX IF NOT EXISTS idx_topics_trend   ON topics(trend_score DESC);

            CREATE TABLE IF NOT EXISTS article_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
                topic_id   INTEGER NOT NULL REFERENCES topics(id)   ON DELETE CASCADE,
                similarity REAL NOT NULL DEFAULT 0.0,
                UNIQUE(article_id, topic_id)
            );

            CREATE INDEX IF NOT EXISTS idx_article_topics_article ON article_topics(article_id);
            CREATE INDEX IF NOT EXISTS idx_article_topics_topic   ON article_topics(topic_id);

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
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """
    Inkrementális séma migráció: csak akkor futtat ALTER TABLE-t,
    ha az adott oszlop még nem létezik.
    """
    existing = {
        row[1]
        for row in conn.execute("PRAGMA table_info(articles)").fetchall()
    }
    if "relevance_score" not in existing:
        conn.execute(
            "ALTER TABLE articles ADD COLUMN relevance_score REAL NOT NULL DEFAULT 0.0"
        )


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def sync_sources(feeds: list[dict]) -> None:
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
                (feed["name"], feed["lang"], feed.get("country", ""),
                 feed.get("category", "hirek"), feed["rss"]),
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
        return conn.execute(
            "SELECT 1 FROM articles WHERE url = ? LIMIT 1", (url,)
        ).fetchone() is not None


def hash_exists(content_hash: str) -> bool:
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM articles WHERE content_hash = ? LIMIT 1", (content_hash,)
        ).fetchone() is not None


def save_article(item: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO articles (
                url, title, source, lang, country, category, published,
                scraped_at, content, content_hu, content_hash, mini_summary_hu
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (item["link"], item["title"], item["source"], item["lang"],
             item.get("country", ""), item.get("category", "hirek"),
             item.get("published", ""), datetime.now(timezone.utc).isoformat(),
             item["clean_text"], item["clean_text_hu"],
             item["content_hash"], item["mini_summary_hu"]),
        )


def get_article_id(url: str) -> int | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM articles WHERE url = ? LIMIT 1", (url,)
        ).fetchone()
        return row["id"] if row else None


def update_relevance_score(article_id: int, score: float) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE articles SET relevance_score = ? WHERE id = ?", (score, article_id)
        )


def list_articles_since(cutoff_iso: str, limit: int = 200) -> list[dict]:
    """
    Visszaadja a cutoff_iso utáni cikkeket relevancia-score szerint,
    keywords, entities és topics mezőkkel kiegészítve.
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
            SELECT * FROM articles
            WHERE published >= ?
            ORDER BY relevance_score DESC, published DESC
            LIMIT ?
            """,
            (cutoff_normalized, limit),
        ).fetchall()
        articles = [dict(row) for row in rows]

    for article in articles:
        article["keywords"] = get_keywords_for_article(article["id"])
        article["entities"] = get_entities_for_article(article["id"])
        article["topics"]   = get_topics_for_article(article["id"])

    return articles


# ---------------------------------------------------------------------------
# Keywords
# ---------------------------------------------------------------------------

def save_keywords(article_id: int, keywords: list[dict]) -> None:
    with get_conn() as conn:
        for kw in keywords:
            conn.execute(
                "INSERT OR IGNORE INTO article_keywords (article_id, keyword, score) VALUES (?, ?, ?)",
                (article_id, kw["keyword"], kw.get("score", 0.0)),
            )


def get_keywords_for_article(article_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT keyword, score FROM article_keywords WHERE article_id = ? ORDER BY score DESC",
            (article_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_top_keywords_since(cutoff_iso: str, limit: int = 40) -> list[dict]:
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
            SELECT ak.keyword, COUNT(*) AS count, AVG(ak.score) AS avg_score
            FROM article_keywords ak
            JOIN articles a ON a.id = ak.article_id
            WHERE a.published >= ?
            GROUP BY ak.keyword
            ORDER BY count DESC, avg_score DESC
            LIMIT ?
            """,
            (cutoff_normalized, limit),
        ).fetchall()
        return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------

def save_entities(article_id: int, entities: list[dict]) -> None:
    with get_conn() as conn:
        for ent in entities:
            conn.execute(
                "INSERT OR IGNORE INTO article_entities (article_id, entity_text, entity_type, score) VALUES (?, ?, ?, ?)",
                (article_id, ent["text"], ent["type"], ent.get("score", 0.0)),
            )


def get_entities_for_article(article_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT entity_text, entity_type, score FROM article_entities WHERE article_id = ? ORDER BY score DESC",
            (article_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_top_entities_since(cutoff_iso: str, limit: int = 30) -> list[dict]:
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
            SELECT ae.entity_text, ae.entity_type, COUNT(*) AS count, AVG(ae.score) AS avg_score
            FROM article_entities ae
            JOIN articles a ON a.id = ae.article_id
            WHERE a.published >= ?
            GROUP BY ae.entity_text, ae.entity_type
            ORDER BY count DESC, avg_score DESC
            LIMIT ?
            """,
            (cutoff_normalized, limit),
        ).fetchall()
        return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------

def save_topics(window: str, topics: list[dict]) -> list[int]:
    """
    Elmenti a kiszámított témákat és visszaadja az INSERT-elt id-kat.

    Args:
        window: Időablak azonosítója ("12h", "24h", "7d").
        topics: Lista dict-ekből; minden elem:
                {label, keywords (vesszős string), article_count, trend_score}

    Returns:
        Az újonnan beszúrt topic id-k listája (azonos sorrendben).
    """
    now = datetime.now(timezone.utc).isoformat()
    ids: list[int] = []
    with get_conn() as conn:
        for topic in topics:
            cur = conn.execute(
                """
                INSERT INTO topics (window, created_at, label, keywords, article_count, trend_score)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (window, now, topic["label"], topic["keywords"],
                 topic["article_count"], topic.get("trend_score", 0.0)),
            )
            ids.append(cur.lastrowid)
    return ids


def save_article_topics(article_id: int, topic_assignments: list[dict]) -> None:
    """
    Elmenti a cikk–téma kapcsolatokat.

    Args:
        article_id:         Az articles tábla id mezője.
        topic_assignments:  Lista dict-ekből: {topic_id, similarity}.
    """
    with get_conn() as conn:
        for ta in topic_assignments:
            conn.execute(
                "INSERT OR IGNORE INTO article_topics (article_id, topic_id, similarity) VALUES (?, ?, ?)",
                (article_id, ta["topic_id"], ta["similarity"]),
            )


def get_topics_for_article(article_id: int) -> list[dict]:
    """Visszaadja egy cikk témáit similarity szerint csökkenő sorrendben."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT t.id, t.label, t.keywords, t.trend_score, at.similarity
            FROM article_topics at
            JOIN topics t ON t.id = at.topic_id
            WHERE at.article_id = ?
            ORDER BY at.similarity DESC
            """,
            (article_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_topics_since(cutoff_iso: str) -> list[dict]:
    """
    Visszaadja az időablakon belül keletkezett témákat trend_score szerint,
    az egyes témákhoz tartozó legjobb 3 cikkcímmel együtt.
    """
    try:
        dt = datetime.fromisoformat(cutoff_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        cutoff_normalized = dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        cutoff_normalized = cutoff_iso

    with get_conn() as conn:
        topics = [
            dict(row) for row in conn.execute(
                """
                SELECT * FROM topics
                WHERE created_at >= ?
                ORDER BY trend_score DESC
                """,
                (cutoff_normalized,),
            ).fetchall()
        ]
        for topic in topics:
            rows = conn.execute(
                """
                SELECT a.title, a.source, a.published, at.similarity
                FROM article_topics at
                JOIN articles a ON a.id = at.article_id
                WHERE at.topic_id = ?
                ORDER BY at.similarity DESC
                LIMIT 3
                """,
                (topic["id"],),
            ).fetchall()
            topic["top_articles"] = [dict(r) for r in rows]

    return topics


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

def save_summary(window: str, content_md: str, html: str, source_count: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO summaries (window, created_at, content_md, html, source_count) VALUES (?, ?, ?, ?, ?)",
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
                stage=excluded.stage, progress=excluded.progress, message=excluded.message,
                html=excluded.html, error=excluded.error, stats=excluded.stats,
                updated_at=excluded.updated_at
            """,
            (job_id, stage, progress, message, html, error, stats, now, now),
        )


def get_job(job_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return dict(row) if row else None


def get_active_job() -> dict | None:
    running = ("rss", "scrape", "ner", "keywords", "relevance", "topics", "markdown", "ollama", "html")
    placeholders = ",".join("?" * len(running))
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT * FROM jobs WHERE stage IN ({placeholders}) ORDER BY created_at DESC LIMIT 1",
            running,
        ).fetchone()
        return dict(row) if row else None
