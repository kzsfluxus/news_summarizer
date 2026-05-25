"""
Témamodellezés TF-IDF + cosine similarity alapján.

SIMILARITY_THRESHOLD = 0.08
  A valós adatokon mért cosine similarity eloszlás alapján beállított érték.
  44 feldolgozott cikken a legtöbb valódi témapár (Las Vegas doppingverseny × 2,
  Erdogan-tüntetések × 2, Ukrajna-Oroszország × 2, Trump-Irán × 3) 0.08–0.58
  közé esik. A 0.12-es küszöb túl kevés párt hagyott át (8 db), 0.08 mellett
  29 pár kerül be, ami elegendő klaszterképzéshez.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict

SIMILARITY_THRESHOLD = 0.08
MIN_CLUSTER_SIZE     = 2
MAX_LABEL_TERMS      = 4
MAX_TOPICS           = 12

STOPWORDS = {
    "a", "az", "és", "is", "de", "nem", "egy", "hogy", "ez", "van",
    "volt", "lesz", "már", "még", "csak", "el", "meg", "ki", "be", "fel",
    "le", "át", "rá", "én", "te", "ő", "mi", "ti", "ők", "azt", "ezt",
    "mint", "ha", "sem", "vagy", "mert", "amikor", "ahol", "aki", "ami",
    "the", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "was", "are", "were", "be", "been",
    "that", "this", "it", "as", "not", "also", "more", "its", "their",
}

TOKEN_RE = re.compile(r"[^\w\s]", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    text = TOKEN_RE.sub(" ", text.lower())
    return [t for t in text.split() if len(t) >= 3 and t not in STOPWORDS]


def _build_tfidf(docs: list[list[str]]) -> list[dict[str, float]]:
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
    Single-pass klaszterezés: minden dokumentumot a leghasonlóbb
    már létező klaszterhez rendel, vagy új klasztert nyit.

    Az iteratív centroid-alapú módszer nem működik, mert az inicializáláskor
    minden pont saját klasztere, és a saját centroid-similarity = 1.0,
    tehát soha nem lép fel klaszterváltás. A single-pass ezt elkerüli.
    """
    # Lista: (centroid_vec, [member_indices])
    cluster_centers: list[tuple[dict[str, float], list[int]]] = []

    for idx, vec in enumerate(vectors):
        best_ci = -1
        best_sim = SIMILARITY_THRESHOLD
        for ci, (centroid, _) in enumerate(cluster_centers):
            sim = _cosine(vec, centroid)
            if sim > best_sim:
                best_sim = sim
                best_ci = ci

        if best_ci >= 0:
            cluster_centers[best_ci][1].append(idx)
            # Centroid frissítése az új taggal
            members = cluster_centers[best_ci][1]
            merged: dict[str, float] = defaultdict(float)
            for m in members:
                for term, score in vectors[m].items():
                    merged[term] += score
            cnt = len(members)
            cluster_centers[best_ci] = (
                {t: s / cnt for t, s in merged.items()},
                members,
            )
        else:
            cluster_centers.append((dict(vec), [idx]))

    return [members for _, members in cluster_centers if len(members) >= MIN_CLUSTER_SIZE]


def _cluster_label(members: list[int], vectors: list[dict[str, float]]) -> str:
    merged: dict[str, float] = defaultdict(float)
    for idx in members:
        for term, score in vectors[idx].items():
            merged[term] += score
    top = sorted(merged.items(), key=lambda x: x[1], reverse=True)[:MAX_LABEL_TERMS]
    return " · ".join(t.capitalize() for t, _ in top)


def _trend_score(members: list[int], articles: list[dict]) -> float:
    scores = [articles[i].get("relevance_score", 0.0) for i in members]
    avg = sum(scores) / max(len(scores), 1)
    return round(avg * math.log(len(members) + 1), 4)


def compute_topics(articles: list[dict], window: str) -> tuple[list[dict], list[dict]]:
    if not articles:
        return [], []

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

    clusters_with_trend = sorted(
        [(m, _trend_score(m, articles)) for m in clusters],
        key=lambda x: x[1], reverse=True
    )[:MAX_TOPICS]

    topics: list[dict] = []
    assignments: list[dict] = []

    for topic_idx, (members, trend) in enumerate(clusters_with_trend):
        label = _cluster_label(members, vectors)
        merged: dict[str, float] = defaultdict(float)
        for idx in members:
            for term, score in vectors[idx].items():
                merged[term] += score
        top_kw = sorted(merged.items(), key=lambda x: x[1], reverse=True)[:8]
        topics.append({
            "label": label,
            "keywords": ", ".join(t for t, _ in top_kw),
            "article_count": len(members),
            "trend_score": trend,
        })
        centroid: dict[str, float] = defaultdict(float)
        for idx in members:
            for term, score in vectors[idx].items():
                centroid[term] += score
        c_norm = {t: s / len(members) for t, s in centroid.items()}
        for idx in members:
            assignments.append({
                "article_index": idx,
                "topic_index": topic_idx,
                "similarity": round(_cosine(vectors[idx], c_norm), 4),
            })

    return topics, assignments
