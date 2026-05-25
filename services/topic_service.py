"""
Témamodellezés TF-IDF + cosine similarity alapján.

Módszer:
  1. A cikkek mini_summary_hu és kulcsszó mezőiből TF-IDF vektort számítunk.
  2. Cosine similarity alapján az összes cikket összehasonlítjuk egymással.
  3. Agglomeratív klaszterezéssel (average linkage, similarity küszöb alapján)
     témaklubbokat képzünk.
  4. Minden klaszter kap egy automatikus címkét a legsúlyosabb TF-IDF termek alapján.
  5. A trend_score az adott téma cikkeinek átlagos relevancia-score-ja,
     a klaszter méretével felszorozva – így a sok forrásban megjelenő,
     friss témák kerülnek előre.

Előnyök és korlátok:
  + Teljesen offline, gyors, nincs nagy modell
  + Magyar szövegen is jól működik
  - Nem szemantikus: hasonló értelmű, de eltérő szavak külön klaszterbe kerülhetnek
  - Az optimális küszöb (SIMILARITY_THRESHOLD) szövegtől függ, kísérletezés szükséges

Hangolható paraméterek (ide vagy config.py-ba vihetők):
  SIMILARITY_THRESHOLD  – klaszterezési küszöb (0.0–1.0)
  MIN_CLUSTER_SIZE      – legalább ennyi cikk kell egy témához
  MAX_LABEL_TERMS       – téma-címkében szereplő szavak száma
  MAX_TOPICS            – maximálisan visszaadott témák száma
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import datetime, timezone

SIMILARITY_THRESHOLD = 0.25   # Ennél kisebb cosine similarity → különböző téma
MIN_CLUSTER_SIZE     = 2      # Legalább 2 cikk kell egy témához
MAX_LABEL_TERMS      = 4      # Téma-feliratban ennyi szó
MAX_TOPICS           = 12     # Maximálisan visszaadott témák

# Magyar és angol stopszavak; nem teljes lista, de lefedi a leggyakoribb eseteket
STOPWORDS = {
    "a", "az", "és", "is", "de", "nem", "egy", "hogy", "ez", "az", "van",
    "volt", "lesz", "már", "még", "csak", "el", "meg", "ki", "be", "fel",
    "le", "át", "rá", "én", "te", "ő", "mi", "ti", "ők", "azt", "ezt",
    "mint", "ha", "sem", "vagy", "mert", "amikor", "ahol", "aki", "ami",
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "was", "are", "were", "be", "been",
    "that", "this", "it", "as", "not", "also", "more", "its", "their",
}

TOKEN_RE = re.compile(r"[^\w\s]", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    """Kisbetűsít, interpunkciót eltávolít, stopszavakat szűr, min. 3 karakter."""
    text = TOKEN_RE.sub(" ", text.lower())
    return [
        t for t in text.split()
        if len(t) >= 3 and t not in STOPWORDS
    ]


def _build_tfidf(docs: list[list[str]]) -> list[dict[str, float]]:
    """
    Kiszámítja a TF-IDF vektorokat.

    TF  = term_count / doc_length
    IDF = log(N / (1 + df))  – simított, hogy a nulla-df termeket is kezelje

    Returns:
        Lista dict-ekből; minden dict {term: tfidf_score} egy dokumentumhoz.
    """
    n = len(docs)
    df: dict[str, int] = defaultdict(int)
    for doc in docs:
        for term in set(doc):
            df[term] += 1

    vectors: list[dict[str, float]] = []
    for doc in docs:
        tf: dict[str, float] = defaultdict(float)
        for term in doc:
            tf[term] += 1
        doc_len = max(len(doc), 1)
        vec: dict[str, float] = {}
        for term, count in tf.items():
            idf = math.log(n / (1 + df[term])) + 1.0
            vec[term] = (count / doc_len) * idf
        vectors.append(vec)

    return vectors


def _cosine(v1: dict[str, float], v2: dict[str, float]) -> float:
    """Cosine similarity két TF-IDF vektor között."""
    common = set(v1) & set(v2)
    if not common:
        return 0.0
    dot = sum(v1[t] * v2[t] for t in common)
    norm1 = math.sqrt(sum(s * s for s in v1.values()))
    norm2 = math.sqrt(sum(s * s for s in v2.values()))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def _cluster(vectors: list[dict[str, float]]) -> list[list[int]]:
    """
    Mohó agglomeratív klaszterezés SIMILARITY_THRESHOLD alapján.

    Minden dokumentum először saját klaszterbe kerül.
    Ezután minden dokumentumot ahhoz a klaszterhez rendeljük,
    amelynek centroidjával a legmagasabb a cosine hasonlósága,
    feltéve, hogy meghaladja a küszöböt.

    A centroid az egyes klasztertagok TF-IDF vektorainak átlaga.
    """
    n = len(vectors)
    assignments = list(range(n))  # Kezdetben mindenki saját klaszterben

    changed = True
    while changed:
        changed = False
        # Klaszter-centroidok számítása
        clusters: dict[int, list[int]] = defaultdict(list)
        for idx, cid in enumerate(assignments):
            clusters[cid].append(idx)

        centroids: dict[int, dict[str, float]] = {}
        for cid, members in clusters.items():
            merged: dict[str, float] = defaultdict(float)
            for m in members:
                for term, score in vectors[m].items():
                    merged[term] += score
            count = len(members)
            centroids[cid] = {t: s / count for t, s in merged.items()}

        # Újrarendelés
        for idx in range(n):
            best_cid = assignments[idx]
            best_sim = SIMILARITY_THRESHOLD
            for cid, centroid in centroids.items():
                sim = _cosine(vectors[idx], centroid)
                if sim > best_sim:
                    best_sim = sim
                    best_cid = cid
            if best_cid != assignments[idx]:
                assignments[idx] = best_cid
                changed = True

    # Klaszterek összegyűjtése
    result: dict[int, list[int]] = defaultdict(list)
    for idx, cid in enumerate(assignments):
        result[cid].append(idx)

    return [members for members in result.values() if len(members) >= MIN_CLUSTER_SIZE]


def _cluster_label(members: list[int], vectors: list[dict[str, float]]) -> str:
    """
    Automatikus téma-felirat: a klaszter tagjainak összesített TF-IDF súlyai
    alapján a legsúlyosabb MAX_LABEL_TERMS term, nagybetűsítve.
    """
    merged: dict[str, float] = defaultdict(float)
    for idx in members:
        for term, score in vectors[idx].items():
            merged[term] += score
    top = sorted(merged.items(), key=lambda x: x[1], reverse=True)[:MAX_LABEL_TERMS]
    return " · ".join(t.capitalize() for t, _ in top)


def _trend_score(members: list[int], articles: list[dict]) -> float:
    """
    Trend-score: a klaszter tagjainak átlagos relevancia-score-ja
    szorozva a log(klaszter mérete + 1) értékkel.

    A logaritmikus méretfaktor biztosítja, hogy a nagy klaszterek
    ne söpörjék el teljesen a kis, de releváns témákat.
    """
    scores = [articles[i].get("relevance_score", 0.0) for i in members]
    avg = sum(scores) / max(len(scores), 1)
    size_factor = math.log(len(members) + 1)
    return round(avg * size_factor, 4)


def compute_topics(articles: list[dict], window: str) -> tuple[list[dict], list[dict]]:
    """
    Kiszámítja az időablakon belüli témákat és a cikk–téma hozzárendeléseket.

    A szövegbemenet: mini_summary_hu + a cikk kulcsszavainak space-szel
    összefűzött stringje. A kulcsszavak hozzáadása erősíti a szemantikailag
    fontos termek súlyát a TF-IDF vektorban.

    Args:
        articles: Cikkek listája (keywords és relevance_score mezőkkel).
        window:   Időablak azonosítója (csak a topics táblában tárolódik).

    Returns:
        (topics, assignments) tuple:
          topics:      Lista dict-ekből a topics táblához
                       {label, keywords, article_count, trend_score}
          assignments: Lista dict-ekből az article_topics táblához
                       {article_index, topic_index, similarity}
                       (article_index = articles lista indexe, nem DB id)
    """
    if not articles:
        return [], []

    # Szöveg előkészítés: summary + kulcsszavak
    docs_text = []
    for art in articles:
        kw_str = " ".join(kw["keyword"] for kw in art.get("keywords", []))
        combined = f"{art.get('mini_summary_hu', '')} {kw_str}"
        docs_text.append(combined)

    tokenized = [_tokenize(t) for t in docs_text]
    vectors = _build_tfidf(tokenized)

    clusters = _cluster(vectors)
    if not clusters:
        return [], []

    # Rendezés trend szerint
    clusters_with_trend = [
        (members, _trend_score(members, articles))
        for members in clusters
    ]
    clusters_with_trend.sort(key=lambda x: x[1], reverse=True)
    clusters_with_trend = clusters_with_trend[:MAX_TOPICS]

    topics: list[dict] = []
    assignments: list[dict] = []

    for topic_idx, (members, trend) in enumerate(clusters_with_trend):
        label = _cluster_label(members, vectors)

        # Top kulcsszavak a téma leírásához (az összesített TF-IDF top 8 terme)
        merged: dict[str, float] = defaultdict(float)
        for idx in members:
            for term, score in vectors[idx].items():
                merged[term] += score
        top_kw = sorted(merged.items(), key=lambda x: x[1], reverse=True)[:8]
        keywords_str = ", ".join(t for t, _ in top_kw)

        topics.append({
            "label": label,
            "keywords": keywords_str,
            "article_count": len(members),
            "trend_score": trend,
        })

        # Centroid számítás az assignment similarityhez
        centroid: dict[str, float] = defaultdict(float)
        for idx in members:
            for term, score in vectors[idx].items():
                centroid[term] += score
        c_count = len(members)
        centroid_norm = {t: s / c_count for t, s in centroid.items()}

        for idx in members:
            sim = _cosine(vectors[idx], centroid_norm)
            assignments.append({
                "article_index": idx,
                "topic_index": topic_idx,
                "similarity": round(sim, 4),
            })

    return topics, assignments
