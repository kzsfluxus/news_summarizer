"""
Kulcsszókinyerés KeyBERT segítségével.

Modell: paraphrase-multilingual-MiniLM-L12-v2 (~120 MB)
  – Többnyelvű sentence-transformer modell
  – Jól teljesít magyar szövegen is
  – CPU-n is gyors, GPU-val még gyorsabb
  – Első indításkor töltődik le; utána cache-eli

A KeyBERT szemantikus hasonlóság alapján választja ki a legjellemzőbb
kulcsszavakat és kifejezéseket. Ez pontosabb eredményt ad magyar szövegen,
mint a statisztikai alapú YAKE, de lassabb (CPU-n ~1-3 mp/cikk).

Kulcsszó-kandidátus hossza: 1-2 szó (unigram + bigram).
Cikkenként legfeljebb MAX_KEYWORDS kulcsszó kerül tárolásra.
"""

from __future__ import annotations

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# Sentence-transformer modell neve
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

# Kinyert kulcsszavak maximális száma cikkenként
MAX_KEYWORDS = 10

# Minimális KeyBERT relevancia-score; ez alatt nem tároljuk a kulcsszót
SCORE_THRESHOLD = 0.2

# Szókapcsolat hossza (unigram + bigram)
KEYPHRASE_NGRAM_RANGE = (1, 2)

# Diverzitás szabályozása: 0.0 = legrelevásabb (redundáns lehet),
# 1.0 = maximálisan változatos; 0.5 jó egyensúly
DIVERSITY = 0.5


@lru_cache(maxsize=1)
def _load_model():
    """
    Lazy betöltés lru_cache-sel: csak az első híváskor töltődik be,
    utána memóriában marad a folyamat életciklusa alatt.

    Raises:
        ImportError: Ha a keybert vagy sentence_transformers nincs telepítve.
    """
    try:
        from keybert import KeyBERT
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise ImportError(
            "Hiányzó csomag. Telepítsd: pip install keybert sentence-transformers"
        ) from e

    logger.info("KeyBERT modell betöltése: %s", MODEL_NAME)
    st_model = SentenceTransformer(MODEL_NAME)
    model = KeyBERT(model=st_model)
    logger.info("KeyBERT modell betöltve.")
    return model


def extract_keywords(text: str) -> list[dict]:
    """
    Kulcsszavakat kinyeri a szövegből KeyBERT segítségével.

    A Max Marginal Relevance (MMR) algoritmust alkalmazza, hogy a
    kulcsszavak egyszerre relevánsak és változatosak legyenek.

    Args:
        text: A feldolgozandó szöveg (tipikusan content_hu).

    Returns:
        Lista dict-ekből: [{"keyword": str, "score": float}, ...]
        Score szerint csökkenő sorrendben, SCORE_THRESHOLD felett.
        Üres lista, ha a modell betöltése sikertelen vagy nincs találat.
    """
    if not text or not text.strip():
        return []

    try:
        model = _load_model()
    except Exception as exc:
        logger.error("KeyBERT modell betöltési hiba: %s", exc)
        return []

    try:
        raw = model.extract_keywords(
            text,
            keyphrase_ngram_range=KEYPHRASE_NGRAM_RANGE,
            stop_words=None,        # Nincs beépített magyar stopword lista;
                                    # a szemantikus szűrés ezt részben kompenzálja
            use_mmr=True,           # Max Marginal Relevance: relevancia + diverzitás
            diversity=DIVERSITY,
            top_n=MAX_KEYWORDS,
        )
    except Exception as exc:
        logger.warning("KeyBERT kinyerési hiba: %s", exc)
        return []

    return [
        {"keyword": kw.strip(), "score": round(float(score), 4)}
        for kw, score in raw
        if score >= SCORE_THRESHOLD and kw.strip()
    ]
