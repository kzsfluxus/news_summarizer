"""
Relevancia-score számítás.

A score négy összetevőből áll, mindegyik 0.0–1.0 közé normalizált,
súlyozott összegként:

  1. source_score    – hány különböző forrásban jelent meg hasonló cikk
                       (ugyanazon kulcsszavak alapján)
  2. recency_score   – frissesség: minél újabb, annál magasabb
  3. entity_score    – entitások átlagos konfidenciája és száma
  4. keyword_score   – kulcsszavak átlagos relevancia-értéke

Súlyok (összegük 1.0):
  SOURCE_WEIGHT   = 0.35  – legfontosabb: ha több forrás is ír róla, valóban fontos
  RECENCY_WEIGHT  = 0.25  – friss hírek előnyben
  ENTITY_WEIGHT   = 0.25  – gazdag entitásprofil = informatív cikk
  KEYWORD_WEIGHT  = 0.15  – kulcsszó-relevancia kisebb súllyal

A súlyok config.py-ba is kivezethetők, ha finomhangolás szükséges.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone


SOURCE_WEIGHT  = 0.35
RECENCY_WEIGHT = 0.25
ENTITY_WEIGHT  = 0.25
KEYWORD_WEIGHT = 0.15

# Forrás-score telítési küszöb: ennyi különböző forrásnál éri el a maximumot
MAX_SOURCES = 5

# Frissességi felezési idő órákban: ennyi óra után feleződik a recency_score
RECENCY_HALF_LIFE_HOURS = 12.0


def _recency_score(published_iso: str) -> float:
    """
    Exponenciális bomlás alapján számít frissességi score-t.

    score = exp(-ln(2) * age_hours / half_life)

    Például:
      0 óra  → 1.0
      12 óra → 0.5
      24 óra → 0.25
      48 óra → 0.06
    """
    if not published_iso:
        return 0.0
    try:
        dt = datetime.fromisoformat(published_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
        return math.exp(-math.log(2) * age_hours / RECENCY_HALF_LIFE_HOURS)
    except (ValueError, OSError):
        return 0.0


def _source_score(article: dict, all_articles: list[dict]) -> float:
    """
    Megbecsüli, hány különböző forrásban jelent meg az adott témájú hír
    a kulcsszavak átfedése alapján.

    Módszer: az aktuális cikk kulcsszavait összeveti a többi cikk
    kulcsszavaival; ha legalább 1 közös kulcsszó van, más forrásnak számít.

    Visszatér 0.0–1.0 között, MAX_SOURCES-szal normalizálva.
    """
    my_keywords = {kw["keyword"] for kw in article.get("keywords", [])}
    if not my_keywords:
        return 0.0

    my_source = article.get("source", "")
    matching_sources: set[str] = {my_source}

    for other in all_articles:
        if other["id"] == article["id"]:
            continue
        other_keywords = {kw["keyword"] for kw in other.get("keywords", [])}
        if my_keywords & other_keywords:  # van közös kulcsszó
            matching_sources.add(other.get("source", ""))

    source_count = len(matching_sources)
    return min(source_count / MAX_SOURCES, 1.0)


def _entity_score(entities: list[dict]) -> float:
    """
    Entitás-alapú score: az entitások száma és átlagos konfidenciája alapján.

    score = tanh(count / 5) * avg_confidence

    A tanh telíti a score-t nagy entitásszámnál (5 felett alig nő tovább),
    az avg_confidence a minőséget fejezi ki.
    """
    if not entities:
        return 0.0
    avg_conf = sum(e.get("score", 0.0) for e in entities) / len(entities)
    count_factor = math.tanh(len(entities) / 5.0)
    return count_factor * avg_conf


def _keyword_score(keywords: list[dict]) -> float:
    """
    Kulcsszó-alapú score: a top-5 kulcsszó átlagos relevancia-értéke.

    Csak a legmagasabb score-ú 5 kulcsszót veszi figyelembe,
    hogy a hosszú cikkek ne kapjanak automatikusan magasabb pontszámot.
    """
    if not keywords:
        return 0.0
    top = sorted(keywords, key=lambda k: k.get("score", 0.0), reverse=True)[:5]
    return sum(k.get("score", 0.0) for k in top) / len(top)


def compute_relevance(article: dict, all_articles: list[dict]) -> float:
    """
    Kiszámítja egy cikk relevanciáját a többi cikkhez viszonyítva.

    Args:
        article:      Az értékelendő cikk dict-je (keywords és entities mezőkkel).
        all_articles: Az időablakon belüli összes cikk (source_score-hoz kell).

    Returns:
        0.0–1.0 közötti float relevancia-score.
    """
    s_score = _source_score(article, all_articles)
    r_score = _recency_score(article.get("published", ""))
    e_score = _entity_score(article.get("entities", []))
    k_score = _keyword_score(article.get("keywords", []))

    return round(
        SOURCE_WEIGHT  * s_score +
        RECENCY_WEIGHT * r_score +
        ENTITY_WEIGHT  * e_score +
        KEYWORD_WEIGHT * k_score,
        4,
    )


def compute_and_update_batch(articles: list[dict]) -> list[dict]:
    """
    Kiszámítja az összes cikk relevancia-score-ját egyszerre.

    Azért kell batch-ben számolni, mert a source_score az összes
    többi cikkhez viszonyítva értékel.

    Args:
        articles: Cikkek listája keywords és entities mezőkkel.

    Returns:
        Ugyanaz a lista, relevance_score mezővel kiegészítve.
    """
    for article in articles:
        article["relevance_score"] = compute_relevance(article, articles)
    return articles
