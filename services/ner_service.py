"""
Entitáskinyerés GLiNER segítségével.

Modell: enyaml/gliner-multi-v2.1
  – Többnyelvű zero-shot NER modell (~400 MB)
  – Futtatható CPU-n is, de GPU-val lényegesen gyorsabb
  – Első indításkor letölti a Hugging Face hub-ról; utána cache-eli

Felismert entitástípusok:
  PERSON       – Személyek (politikusok, közszereplők)
  ORG          – Szervezetek, intézmények, cégek
  LOCATION     – Helyek, városok, országok
  EVENT        – Események, konferenciák, háborúk
  PRODUCT      – Termékek, technológiák

A NER a content_hu mezőn fut (teljes fordított szöveg), mert
az összefoglalónál pontosabb entitás-lefedettséget ad, igaz, lassabb.

Teljesítmény: CPU-n ~2-8 mp/cikk a szöveg hosszától függően.
Ha ez szűk keresztmetszet, váltani lehet mini_summary_hu-ra (config-ban).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

# Felismert entitástípusok – a GLiNER zero-shot, ezért szabadon bővíthető.
# Új típus hozzáadásához csak ebbe a listába kell felvenni.
ENTITY_LABELS = [
    "person",
    "organization",
    "location",
    "event",
    "product",
]

# Konfidencia küszöb: ennél alacsonyabb score-ú entitásokat eldobjuk.
# 0.4 elfogadható egyensúly pontosság és lefedettség között;
# szigorúbb szűréshez emelhető 0.5-re.
SCORE_THRESHOLD = 0.4

# GLiNER belső tokenkorlát; ennél hosszabb szöveg ablakokra bontódik.
# A modell max 512 token inputot kezel egyszerre.
MAX_CHUNK_CHARS = 1500


@lru_cache(maxsize=1)
def _load_model():
    """
    Lazy betöltés: az első NER híváskor töltődik be a modell.
    Az lru_cache garantálja, hogy csak egyszer töltődik be a folyamat
    élettartama alatt.

    Raises:
        ImportError: Ha a gliner csomag nincs telepítve.
        OSError:     Ha a modell letöltése sikertelen.
    """
    try:
        from gliner import GLiNER
    except ImportError as e:
        raise ImportError(
            "A gliner csomag hiányzik. Telepítsd: pip install gliner"
        ) from e

    logger.info("GLiNER modell betöltése: enyaml/gliner-multi-v2.1")
    model = GLiNER.from_pretrained("enyaml/gliner-multi-v2.1")
    logger.info("GLiNER modell betöltve.")
    return model


def _chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """
    Mondathatáron osztja fel a szöveget a modell tokenkorlátja miatt.
    Ha nincs megfelelő mondathatár, szóhatáron vágja a szöveget.
    """
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            # Mondathatár keresése visszafelé
            split = text.rfind(". ", start, end)
            if split == -1:
                split = text.rfind(" ", start, end)
            if split > start:
                end = split + 1
        chunks.append(text[start:end].strip())
        start = end
    return [c for c in chunks if c]


def _normalize_type(raw_type: str) -> str:
    """
    Normalizálja az entitástípust egységes nagybetűs formára.
    A GLiNER a prompt-ban megadott stringet adja vissza,
    ezért érdemes egységesíteni.
    """
    mapping = {
        "person": "PERSON",
        "organization": "ORG",
        "organisation": "ORG",
        "location": "LOCATION",
        "event": "EVENT",
        "product": "PRODUCT",
    }
    return mapping.get(raw_type.lower(), raw_type.upper())


def extract_entities(text: str) -> list[dict[str, Any]]:
    """
    Entitásokat kinyeri a szövegből GLiNER segítségével.

    Azonos (text, type) párból csak a legmagasabb score-ú példányt
    tartja meg (deduplikáció).

    Args:
        text: A feldolgozandó szöveg (tipikusan content_hu).

    Returns:
        Lista dict-ekből: [{"text": str, "type": str, "score": float}, ...]
        Score szerint csökkenő sorrendben.
        Üres lista, ha a modell betöltése sikertelen vagy nincs találat.
    """
    if not text or not text.strip():
        return []

    try:
        model = _load_model()
    except Exception as exc:
        logger.error("GLiNER modell betöltési hiba: %s", exc)
        return []

    chunks = _chunk_text(text)
    # Deduplikáció: (text, type) → legjobb score
    best: dict[tuple[str, str], float] = {}

    for chunk in chunks:
        try:
            raw_entities = model.predict_entities(
                chunk,
                ENTITY_LABELS,
                threshold=SCORE_THRESHOLD,
            )
        except Exception as exc:
            logger.warning("GLiNER predikció hiba egy chunkon: %s", exc)
            continue

        for ent in raw_entities:
            entity_text = ent["text"].strip()
            entity_type = _normalize_type(ent["label"])
            score = float(ent.get("score", 0.0))
            key = (entity_text, entity_type)
            if key not in best or score > best[key]:
                best[key] = score

    result = [
        {"text": text, "type": etype, "score": score}
        for (text, etype), score in best.items()
    ]
    result.sort(key=lambda x: x["score"], reverse=True)
    return result
