from __future__ import annotations

import hashlib
import re

import requests
import trafilatura

from config import USER_AGENT

SPACE_RE = re.compile(r"\s+")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


class ScrapeError(RuntimeError):
    pass


def clean_text(text: str) -> str:
    text = text.replace(" ", " ")
    text = SPACE_RE.sub(" ", text)
    paragraphs = [part.strip() for part in text.split("\n") if part.strip()]
    if paragraphs:
        return "\n".join(paragraphs)
    return text.strip()


def extract_main_text(url: str, timeout: int = 20) -> str:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        response = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        downloaded = response.text

    text = trafilatura.extract(
        downloaded,
        url=url,
        favor_precision=True,
        include_comments=False,
        include_tables=False,
        include_links=False,
    )
    if not text:
        raise ScrapeError(f"Nem sikerült főszöveget kinyerni: {url}")
    return clean_text(text)


def fingerprint_text(text: str, prefix_sentences: int = 8) -> str:
    sentences = [s.strip() for s in SENTENCE_RE.split(text) if s.strip()]
    head = " ".join(sentences[:prefix_sentences]) if sentences else text[:1200]
    normalized = SPACE_RE.sub(" ", head.lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def shorten_for_context(text: str, target_chars: int = 1600) -> str:
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
