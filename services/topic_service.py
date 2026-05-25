"""
Témamodellezés TF-IDF + cosine similarity alapján.

SIMILARITY_THRESHOLD csökkentve 0.25 → 0.12: rövid mini_summary_hu szövegeken
(5 mondat + néhány kulcsszó) a magasabb küszöb szinte soha nem teljesül,
ezért 0 klaszter keletkezett. 0.12 mellett a részben átfedő témájú cikkek
is egy klaszterbe kerülnek.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict

SIMILARITY_THRESHOLD = 0.12
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
    n = len(vectors)
    assignments = list(range(n))
    changed = True
    while changed:
        changed = False
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
    result: dict[int, list[int]] = defaultdict(list)
    for idx, cid in enumerate(assignments):
        result[cid].append(idx)
    return [members for members in result.values() if len(members) >= MIN_CLUSTER_SIZE]


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
