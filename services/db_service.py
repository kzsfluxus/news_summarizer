"""
Adatbázis-réteg – SQLite.

Táblák:
  sources           – RSS források
  articles          – Feldolgozott cikkek + relevance_score
  article_keywords  – KeyBERT kulcsszavak
  article_entities  – GLiNER entitások
  topics            – TF-IDF klaszterek
  article_topics    – Cikk–téma kapcsolatok
  articles_fts      – FTS5 virtuális tábla (4. fázis)
  summaries         – Ollama összefoglalók
  jobs              – Pipeline job állapotok

FTS5 stratégia:
  Az articles_fts virtuális táblát INSERT/UPDATE/DELETE triggerek tartják szinkronban
  az articles táblával. A keresés a title, mini_summary_hu és content_hu mezőkön fut,
  amelyek a leginkább informatívak és a legtöbb találatot adják.
  A content_hu teljes szöveg nagy méretű lehet; ha teljesítmény gond lép fel,
  a content_hu kivehető az FTS táblából és a keresés title + mini_summary_hu-ra szűkíthető.
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
            CREATE INDEX IF NOT EXISTS idx_articles_source     ON articles(source);

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

            CREATE INDEX IF NOT EXISTS idx_topics_window ON topics(window);
            CREATE INDEX IF NOT EXISTS idx_topics_trend  ON topics(trend_score DESC);

            CREATE TABLE IF NOT EXISTS article_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
                topic_id   INTEGER NOT NULL REFERENCES topics(id)   ON DELETE CASCADE,
                similarity REAL NOT NULL DEFAULT 0.0,
                UNIQUE(article_id, topic_id)
            );

            CREATE INDEX IF NOT EXISTS idx_article_topics_article ON article_topics(article_id);
            CREATE INDEX IF NOT EXISTS idx_article_topics_topic   ON article_topics(topic_id);

            -- FTS5 virtuális tábla: title, mini_summary_hu, content_hu indexelve
            -- content='' → contentless shadow table; a snippetek generálásához
            -- az eredeti mezőket az articles táblából olvassuk vissza
            CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
                title,
                mini_summary_hu,
                content_hu,
                content='articles',
                content_rowid='id',
                tokenize='unicode61'
            );

            -- Triggerek: articles_fts szinkronizálása articles-szel
            CREATE TRIGGER IF NOT EXISTS articles_fts_insert
            AFTER INSERT ON articles BEGIN
                INSERT INTO articles_fts(rowid, title, mini_summary_hu, content_hu)
                VALUES (new.id, new.title, new.mini_summary_hu, new.content_hu);
            END;

            CREATE TRIGGER IF NOT EXISTS articles_fts_delete
            AFTER DELETE ON articles BEGIN
                INSERT INTO articles_fts(articles_fts, rowid, title, mini_summary_hu, content_hu)
                VALUES ('delete', old.id, old.title, old.mini_summary_hu, old.content_hu);
            END;

            CREATE TRIGGER IF NOT EXISTS articles_fts_update
            AFTER UPDATE ON articles BEGIN
                INSERT INTO articles_fts(articles_fts, rowid, title, mini_summary_hu, content_hu)
                VALUES ('delete', old.id, old.title, old.mini_summary_hu, old.content_hu);
                INSERT INTO articles_fts(rowid, title, mini_summary_hu, content_hu)
                VALUES (new.id, new.title, new.mini_summary_hu, new.content_hu);
            END;

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
    Inkrementális séma migráció.
    Meglévő DB-n is futtatható; csak a hiányzó elemeket adja hozzá.
    """
    existing = {
        row[1]
        for row in conn.execute("PRAGMA table_info(articles)").fetchall()
    }
    if "relevance_score" not in existing:
        conn.execute(
            "ALTER TABLE articles ADD COLUMN relevance_score REAL NOT NULL DEFAULT 0.0"
        )

    # FTS rebuild meglévő cikkekre, ha az FTS tábla üres de az articles nem
    fts_count = conn.execute("SELECT COUNT(*) FROM articles_fts").fetchone()[0]
    art_count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    if art_count > 0 and fts_count == 0:
        conn.execute(
            """
            INSERT INTO articles_fts(rowid, title, mini_summary_hu, content_hu)
            SELECT id, title, mini_summary_hu, content_hu FROM articles
            """
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
                    lang=excluded.lang, country=excluded.country,
                    category=excluded.category, rss_url=excluded.rss_url
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
            "SELECT 1 FROM articles WHERE url=? LIMIT 1", (url,)
        ).fetchone() is not None


def hash_exists(content_hash: str) -> bool:
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM articles WHERE content_hash=? LIMIT 1", (content_hash,)
        ).fetchone() is not None


def save_article(item: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO articles
              (url, title, source, lang, country, category, published,
               scraped_at, content, content_hu, content_hash, mini_summary_hu)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (item["link"], item["title"], item["source"], item["lang"],
             item.get("country",""), item.get("category","hirek"),
             item.get("published",""), datetime.now(timezone.utc).isoformat(),
             item["clean_text"], item["clean_text_hu"],
             item["content_hash"], item["mini_summary_hu"]),
        )


def get_article_id(url: str) -> int | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM articles WHERE url=? LIMIT 1", (url,)
        ).fetchone()
        return row["id"] if row else None


def get_article_by_id(article_id: int) -> dict | None:
    """Visszaad egy teljes cikket az összes NLP mezőjével."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM articles WHERE id=?", (article_id,)
        ).fetchone()
        if not row:
            return None
        article = dict(row)
    article["keywords"] = get_keywords_for_article(article_id)
    article["entities"] = get_entities_for_article(article_id)
    article["topics"]   = get_topics_for_article(article_id)
    return article


def update_relevance_score(article_id: int, score: float) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE articles SET relevance_score=? WHERE id=?", (score, article_id)
        )


def list_articles_since(cutoff_iso: str, limit: int = 200) -> list[dict]:
    try:
        dt = datetime.fromisoformat(cutoff_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        cutoff = dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        cutoff = cutoff_iso

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM articles WHERE published>=?
            ORDER BY relevance_score DESC, published DESC LIMIT ?
            """,
            (cutoff, limit),
        ).fetchall()
        articles = [dict(r) for r in rows]

    for a in articles:
        a["keywords"] = get_keywords_for_article(a["id"])
        a["entities"] = get_entities_for_article(a["id"])
        a["topics"]   = get_topics_for_article(a["id"])
    return articles


def list_recent_articles(limit: int = 20, offset: int = 0) -> list[dict]:
    """Legfrissebb cikkek lapozáshoz (cikkoldal listázáshoz)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM articles ORDER BY published DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


def count_articles() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]


# ---------------------------------------------------------------------------
# Full-text search (FTS5)
# ---------------------------------------------------------------------------

def search_articles(
    query: str,
    source: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    entity: str | None = None,
    topic_id: int | None = None,
    limit: int = 30,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """
    Teljes szöveges keresés FTS5-tel, opcionális szűrőkkel.

    A keresési kifejezés a FTS5 MATCH szintaxisát használja.
    Egyszerű szóra és idézőjeles kifejezésre egyaránt működik.
    Speciális karaktereket biztonságosan kezeljük: az idézőjeleket
    duplázzuk, hogy ne törjék meg a MATCH szintaxist.

    Args:
        query:    Keresési kifejezés (kötelező, legalább 1 karakter).
        source:   Forrás neve szerinti szűrő (opcionális).
        date_from/date_to: ISO 8601 dátum szerinti szűrő (opcionális).
        entity:   Entitás szöveg szerinti szűrő (opcionális).
        topic_id: Téma ID szerinti szűrő (opcionális).
        limit:    Lapméret.
        offset:   Lapozás eltolása.

    Returns:
        (találatok, összes_találat_száma) tuple.
        A találatok tartalmazzák a bm25 relevancia-score-t (fts_score).
    """
    if not query or not query.strip():
        return [], 0

    # FTS MATCH biztonságos escape: idézőjel duplázás
    safe_query = query.strip().replace('"', '""')

    filters = []
    params: list = [safe_query]

    if source:
        filters.append("a.source = ?")
        params.append(source)
    if date_from:
        filters.append("a.published >= ?")
        params.append(date_from)
    if date_to:
        filters.append("a.published <= ?")
        params.append(date_to)
    if entity:
        filters.append(
            "EXISTS (SELECT 1 FROM article_entities ae "
            "WHERE ae.article_id=a.id AND ae.entity_text LIKE ?)"
        )
        params.append(f"%{entity}%")
    if topic_id:
        filters.append(
            "EXISTS (SELECT 1 FROM article_topics at "
            "WHERE at.article_id=a.id AND at.topic_id=?)"
        )
        params.append(topic_id)

    where_clause = ""
    if filters:
        where_clause = "AND " + " AND ".join(filters)

    sql = f"""
        SELECT a.id, a.title, a.source, a.published, a.url,
               a.mini_summary_hu, a.relevance_score,
               bm25(articles_fts) AS fts_score
        FROM articles_fts
        JOIN articles a ON articles_fts.rowid = a.id
        WHERE articles_fts MATCH ?
        {where_clause}
        ORDER BY fts_score
        LIMIT ? OFFSET ?
    """
    count_sql = f"""
        SELECT COUNT(*) FROM articles_fts
        JOIN articles a ON articles_fts.rowid = a.id
        WHERE articles_fts MATCH ?
        {where_clause}
    """

    with get_conn() as conn:
        try:
            rows = conn.execute(sql, params + [limit, offset]).fetchall()
            total = conn.execute(count_sql, params).fetchone()[0]
        except sqlite3.OperationalError:
            # Hibás FTS szintaxis esetén üres eredmény
            return [], 0

    return [dict(r) for r in rows], total


# ---------------------------------------------------------------------------
# Keywords
# ---------------------------------------------------------------------------

def save_keywords(article_id: int, keywords: list[dict]) -> None:
    with get_conn() as conn:
        for kw in keywords:
            conn.execute(
                "INSERT OR IGNORE INTO article_keywords (article_id,keyword,score) VALUES (?,?,?)",
                (article_id, kw["keyword"], kw.get("score", 0.0)),
            )


def get_keywords_for_article(article_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT keyword,score FROM article_keywords WHERE article_id=? ORDER BY score DESC",
            (article_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_top_keywords_since(cutoff_iso: str, limit: int = 40) -> list[dict]:
    try:
        dt = datetime.fromisoformat(cutoff_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        cutoff = dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        cutoff = cutoff_iso
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT ak.keyword, COUNT(*) AS count, AVG(ak.score) AS avg_score
            FROM article_keywords ak JOIN articles a ON a.id=ak.article_id
            WHERE a.published>=? GROUP BY ak.keyword
            ORDER BY count DESC, avg_score DESC LIMIT ?
            """,
            (cutoff, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------

def save_entities(article_id: int, entities: list[dict]) -> None:
    with get_conn() as conn:
        for ent in entities:
            conn.execute(
                "INSERT OR IGNORE INTO article_entities (article_id,entity_text,entity_type,score) VALUES (?,?,?,?)",
                (article_id, ent["text"], ent["type"], ent.get("score", 0.0)),
            )


def get_entities_for_article(article_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT entity_text,entity_type,score FROM article_entities WHERE article_id=? ORDER BY score DESC",
            (article_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_top_entities_since(cutoff_iso: str, limit: int = 30) -> list[dict]:
    try:
        dt = datetime.fromisoformat(cutoff_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        cutoff = dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        cutoff = cutoff_iso
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT ae.entity_text, ae.entity_type, COUNT(*) AS count, AVG(ae.score) AS avg_score
            FROM article_entities ae JOIN articles a ON a.id=ae.article_id
            WHERE a.published>=?
            GROUP BY ae.entity_text, ae.entity_type
            ORDER BY count DESC, avg_score DESC LIMIT ?
            """,
            (cutoff, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def list_distinct_entities(limit: int = 200) -> list[dict]:
    """Az összes ismert entitás; a keresőszűrő autocomplete-jéhez."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT entity_text, entity_type, COUNT(*) AS count
            FROM article_entities GROUP BY entity_text, entity_type
            ORDER BY count DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------

def save_topics(window: str, topics: list[dict]) -> list[int]:
    now = datetime.now(timezone.utc).isoformat()
    ids: list[int] = []
    with get_conn() as conn:
        for topic in topics:
            cur = conn.execute(
                "INSERT INTO topics (window,created_at,label,keywords,article_count,trend_score) VALUES (?,?,?,?,?,?)",
                (window, now, topic["label"], topic["keywords"],
                 topic["article_count"], topic.get("trend_score", 0.0)),
            )
            ids.append(cur.lastrowid)
    return ids


def save_article_topics(article_id: int, topic_assignments: list[dict]) -> None:
    with get_conn() as conn:
        for ta in topic_assignments:
            conn.execute(
                "INSERT OR IGNORE INTO article_topics (article_id,topic_id,similarity) VALUES (?,?,?)",
                (article_id, ta["topic_id"], ta["similarity"]),
            )


def get_topics_for_article(article_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT t.id, t.label, t.keywords, t.trend_score, at.similarity
            FROM article_topics at JOIN topics t ON t.id=at.topic_id
            WHERE at.article_id=? ORDER BY at.similarity DESC
            """,
            (article_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_topics_since(cutoff_iso: str) -> list[dict]:
    try:
        dt = datetime.fromisoformat(cutoff_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        cutoff = dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        cutoff = cutoff_iso
    with get_conn() as conn:
        topics = [dict(r) for r in conn.execute(
            "SELECT * FROM topics WHERE created_at>=? ORDER BY trend_score DESC",
            (cutoff,),
        ).fetchall()]
        for topic in topics:
            rows = conn.execute(
                """
                SELECT a.id, a.title, a.source, a.published, at.similarity
                FROM article_topics at JOIN articles a ON a.id=at.article_id
                WHERE at.topic_id=? ORDER BY at.similarity DESC LIMIT 5
                """,
                (topic["id"],),
            ).fetchall()
            topic["top_articles"] = [dict(r) for r in rows]
    return topics


def get_topic_by_id(topic_id: int) -> dict | None:
    """Egy téma részletes adatai az összes cikkével együtt."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM topics WHERE id=?", (topic_id,)).fetchone()
        if not row:
            return None
        topic = dict(row)
        rows = conn.execute(
            """
            SELECT a.id, a.title, a.source, a.published, a.url,
                   a.mini_summary_hu, a.relevance_score, at.similarity
            FROM article_topics at JOIN articles a ON a.id=at.article_id
            WHERE at.topic_id=? ORDER BY at.similarity DESC
            """,
            (topic_id,),
        ).fetchall()
        topic["articles"] = [dict(r) for r in rows]
    return topic


def list_all_topics(limit: int = 50) -> list[dict]:
    """Összes téma trend szerint; a témaböngésző oldalhoz."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM topics ORDER BY trend_score DESC, created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

def list_recent_jobs(limit: int = 20) -> list[dict]:
    """Legutóbbi job-ok az admin panelhez."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT job_id,stage,progress,message,error,created_at,updated_at FROM jobs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_db_stats() -> dict:
    """Összesített DB statisztikák az admin panelhez."""
    with get_conn() as conn:
        return {
            "articles":  conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0],
            "keywords":  conn.execute("SELECT COUNT(*) FROM article_keywords").fetchone()[0],
            "entities":  conn.execute("SELECT COUNT(*) FROM article_entities").fetchone()[0],
            "topics":    conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0],
            "summaries": conn.execute("SELECT COUNT(*) FROM summaries").fetchone()[0],
            "sources":   conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0],
            "jobs":      conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
        }


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

def save_summary(window: str, content_md: str, html: str, source_count: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO summaries (window,created_at,content_md,html,source_count) VALUES (?,?,?,?,?)",
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
            INSERT INTO jobs (job_id,stage,progress,message,html,error,stats,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(job_id) DO UPDATE SET
                stage=excluded.stage, progress=excluded.progress, message=excluded.message,
                html=excluded.html, error=excluded.error, stats=excluded.stats,
                updated_at=excluded.updated_at
            """,
            (job_id, stage, progress, message, html, error, stats, now, now),
        )


def get_job(job_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        return dict(row) if row else None


def get_active_job() -> dict | None:
    running = ("rss","scrape","ner","keywords","relevance","topics","markdown","ollama","html")
    ph = ",".join("?" * len(running))
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT * FROM jobs WHERE stage IN ({ph}) ORDER BY created_at DESC LIMIT 1",
            running,
        ).fetchone()
        return dict(row) if row else None
