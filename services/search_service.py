"""
Keresési logika és snippet generálás.

A keresés az FTS5 MATCH operátorra támaszkodik; a szűrők az articles
táblán futnak JOIN-nal. A snippet generálás a találatban szereplő
keresési kifejezés körüli szövegkörnyezetet adja vissza kiemelve.

FTS5 bm25() score: kisebb érték = relevánsabb (negatív float).
Az eredményeket ascending bm25 szerint rendezzük, azaz a leginkább
releváns találatok kerülnek előre.
"""

from __future__ import annotations

import re

from services.db_service import search_articles

# Snippet hossza karakterekben
SNIPPET_CHARS = 200

# Kiemelés HTML tagek (a frontenden stílusozható)
HIGHLIGHT_OPEN  = "<mark>"
HIGHLIGHT_CLOSE = "</mark>"


def _make_snippet(text: str, query: str, max_chars: int = SNIPPET_CHARS) -> str:
    """
    Kivonja a keresési kifejezés környezetét a szövegből és kiemel.

    Ha a kifejezés nem található (pl. FTS stemming miatt), az első
    max_chars karaktert adja vissza.

    Args:
        text:     Forrásszöveg (mini_summary_hu).
        query:    Keresési kifejezés (szóközzel tagolt szavak).
        max_chars: A snippet maximális hossza.

    Returns:
        HTML snippet a kiemelésekkel.
    """
    if not text:
        return ""

    # Első keresési szó megkeresése (a többszavas kifejezés első tagja)
    first_word = re.split(r'\s+', query.strip())[0].strip('"')
    pattern = re.compile(re.escape(first_word), re.IGNORECASE)
    match = pattern.search(text)

    if match:
        start = max(0, match.start() - 60)
        end   = min(len(text), start + max_chars)
        snippet = text[start:end].strip()
        if start > 0:
            snippet = "…" + snippet
        if end < len(text):
            snippet = snippet + "…"
    else:
        snippet = text[:max_chars].strip()
        if len(text) > max_chars:
            snippet += "…"

    # Összes keresési szó kiemelése
    words = [w.strip('"') for w in re.split(r'\s+', query.strip()) if w.strip('"')]
    for word in words:
        if word:
            snippet = re.sub(
                f"({re.escape(word)})",
                f"{HIGHLIGHT_OPEN}\\1{HIGHLIGHT_CLOSE}",
                snippet,
                flags=re.IGNORECASE,
            )

    return snippet


def run_search(
    query: str,
    source: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    entity: str | None = None,
    topic_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    Keresést futtat és visszaadja a lapozott eredményeket snippetekkel.

    Args:
        query:     Keresési kifejezés.
        source:    Forrás neve szerinti szűrő.
        date_from: ISO dátum (YYYY-MM-DD), ettől.
        date_to:   ISO dátum (YYYY-MM-DD), eddig.
        entity:    Entitás szöveg szerinti szűrő.
        topic_id:  Téma ID szerinti szűrő.
        page:      Oldalszám (1-től indexelve).
        page_size: Oldal mérete.

    Returns:
        Dict:
          query, total, page, page_size, pages, results
          results: lista {id, title, source, published, url,
                          snippet, relevance_score, fts_score}
    """
    page = max(1, page)
    offset = (page - 1) * page_size

    results, total = search_articles(
        query=query,
        source=source,
        date_from=date_from,
        date_to=date_to,
        entity=entity,
        topic_id=topic_id,
        limit=page_size,
        offset=offset,
    )

    enriched = []
    for r in results:
        snippet = _make_snippet(r.get("mini_summary_hu", ""), query)
        enriched.append({
            "id":              r["id"],
            "title":           r["title"],
            "source":          r["source"],
            "published":       r.get("published", "")[:10],
            "url":             r.get("url", ""),
            "snippet":         snippet,
            "relevance_score": round(r.get("relevance_score", 0.0), 3),
            "fts_score":       round(r.get("fts_score", 0.0), 4),
        })

    pages = max(1, (total + page_size - 1) // page_size)

    return {
        "query":     query,
        "total":     total,
        "page":      page,
        "page_size": page_size,
        "pages":     pages,
        "results":   enriched,
    }
