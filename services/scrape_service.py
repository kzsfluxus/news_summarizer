"""
Cikk letöltés, szövegtisztítás és szöveg-alapú segédfüggvények.

Fő feladatok:
- Főszöveg kinyerése URL-ből (trafilatura + requests fallback)
- Szövegtisztítás (whitespace, non-breaking space)
- Tartalom-ujjlenyomat generálása duplikátumszűréshez
- Extraktív mini-összefoglaló és kontextusrövidítés
"""

from __future__ import annotations

import hashlib
import re

import requests
import trafilatura

from config import USER_AGENT

# Whitespace normalizáláshoz: egy vagy több szóköz/tab/newline → egy szóköz
SPACE_RE = re.compile(r"\s+")

# Mondathatár-detektor: pont/felkiáltójel/kérdőjel után következő szóköz.
# Nem kezeli a rövidítéseket (pl. "dr. Smith"), de cikk-szövegekre elegendő.
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


class ScrapeError(RuntimeError):
    """Akkor dobódik, ha a főszöveg nem nyerhető ki az URL-ből."""
    pass


def clean_text(text: str) -> str:
    """
    Normalizálja a szöveget:
    - Eltávolítja a non-breaking space karaktereket (\u00a0)
    - Összetömöríti a whitespace-t
    - Üres sorokat kiszűri, bekezdéseket megőrzi
    """
    text = text.replace("\u00a0", " ")  # non-breaking space → normál szóköz
    text = SPACE_RE.sub(" ", text)
    paragraphs = [part.strip() for part in text.split("\n") if part.strip()]
    if paragraphs:
        return "\n".join(paragraphs)
    return text.strip()


def extract_main_text(url: str, timeout: int = 20) -> str:
    """
    Letölti és kinyeri a cikk főszövegét.

    Elsődleges módszer: trafilatura (boilerplate-szűrő).
    Fallback: requests + trafilatura extract (ha a trafilatura fetch sikertelen).

    Args:
        url:     A cikk URL-je.
        timeout: HTTP kérés timeout másodpercben (csak a fallback ágban).

    Returns:
        Tisztított főszöveg.

    Raises:
        ScrapeError: Ha a főszöveg nem nyerhető ki.
    """
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        response = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        downloaded = response.text

    text = trafilatura.extract(
        downloaded,
        url=url,
        favor_precision=True,       # Pontosság előnyben a teljességgel szemben
        include_comments=False,
        include_tables=False,
        include_links=False,
    )
    if not text:
        raise ScrapeError(f"Nem sikerült főszöveget kinyerni: {url}")
    return clean_text(text)


def fingerprint_text(text: str, prefix_sentences: int = 8) -> str:
    """
    Tartalom-ujjlenyomatot generál duplikátumszűréshez.

    Az első `prefix_sentences` mondat SHA-256 hash-ét adja vissza,
    kisbetűsítés és whitespace-normalizálás után. Az első mondatok
    elegendők az ismétlődő cikkek azonosításához, és stabilabbak
    az apró szerkesztői módosításokkal szemben, mint a teljes szöveg hash-e.

    Args:
        text:             A szöveg, amelyet ujjlenyomatozunk.
        prefix_sentences: Hány mondatot vonunk be a hash-be.

    Returns:
        64 karakteres hex string (SHA-256).
    """
    sentences = [s.strip() for s in SENTENCE_RE.split(text) if s.strip()]
    head = " ".join(sentences[:prefix_sentences]) if sentences else text[:1200]
    normalized = SPACE_RE.sub(" ", head.lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def shorten_for_context(text: str, target_chars: int = 1600) -> str:
    """
    Rövidíti a szöveget mondathatáron, megközelítve a `target_chars` hosszt.

    Teljes mondatokat tart meg, nem vágja szét a szöveget.
    Jelenleg a `context_hu` mező feltöltésére használjuk; az Ollama prompt
    jelenleg a rövidebb `mini_summary_hu`-t használja, de ez a mező
    jövőbeli NLP feldolgozásra fenntartott.
    """
    if len(text) <= target_chars:
        return text
    sentences = [s.strip() for s in SENTENCE_RE.split(text) if s.strip()]
    parts: list[str] = []
    total = 0
    for sentence in sentences:
        if total + len(sentence) + 1 > target_chars:
            break
        parts.append(sentence)
        total += len(sentence) + 1
    return " ".join(parts) if parts else text[:target_chars].rsplit(" ", 1)[0].strip() + "…"


def extractive_mini_summary(text: str, max_sentences: int = 5, max_chars: int = 900) -> str:
    """
    Extraktív összefoglaló: az első néhány mondatot adja vissza.

    Nem absztraktív – nem értelmezi a szöveget, csak kivágja az elejét.
    Ez elegendő az Ollama prompt kontextusának feltöltéséhez, de a minőség
    függ attól, hogy a cikk eleje tartalmazza-e a lényeget (inverz piramis stílus).

    Args:
        text:          Forrásszöveg (tipikusan a magyar fordítás).
        max_sentences: Maximális mondatszám.
        max_chars:     Kemény karakterkorlát.

    Returns:
        Mondatokból összerakott string.
    """
    sentences = [s.strip() for s in SENTENCE_RE.split(text) if s.strip()]
    if not sentences:
        return text[:max_chars]
    selected = []
    total = 0
    for sentence in sentences:
        if len(selected) >= max_sentences:
            break
        if total + len(sentence) + 1 > max_chars:
            break
        selected.append(sentence)
        total += len(sentence) + 1
    return " ".join(selected) if selected else text[:max_chars]
