"""
RSS feed-ek beolvasása és bejegyzések begyűjtése.

A feedparser könyvtár kétféle dátummezőt adhat vissza:
- String alapú (`published`, `updated`): RFC 2822 formátum, parsedate_to_datetime-mal olvasható
- Struct_time alapú (`published_parsed`, `updated_parsed`): time.mktime-mal konvertálható

Mindkét formátumot kezeljük, mert különböző feed-szoftverek különböző mezőket töltenek ki.
Minden dátumot UTC-re normalizálunk, hogy az időablak-szűrés megbízható legyen.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import time
import re
from typing import Any

import feedparser
import yaml

# Többszörös szóközök összetömörítéséhez (cím-normalizálásban)
SPACE_RE = re.compile(r"\s+")


def normalize_title(value: str) -> str:
    """Kisbetűsíti és whitespace-t normalizálja a címet; feed-szintű duplikátum-szűréshez."""
    return SPACE_RE.sub(" ", (value or "").strip().lower())


def load_feeds(path: str) -> list[dict[str, Any]]:
    """
    Beolvassa a feeds.yaml fájlt.

    Returns:
        Lista dict-ekből; minden dict egy RSS forrást ír le
        (name, lang, country, category, rss kulcsokkal).
    """
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("feeds", [])


def parse_entry_date(entry) -> datetime | None:
    """
    Kinyeri és UTC-re normalizálja a bejegyzés dátumát.

    Feldolgozási sorrend:
    1. `published` / `updated` string mezők (RFC 2822) – parsedate_to_datetime
    2. `published_parsed` / `updated_parsed` struct_time mezők – time.mktime fallback

    A struct_time fallback szükséges, mert egyes feed-ek (pl. Atom) a feedparser
    által már parseolt struct_time-ot adnak vissza string helyett.

    Returns:
        UTC datetime, vagy None ha egyik mező sem értelmezhető.
    """
    for key in ("published", "updated"):
        value = entry.get(key)
        if not value:
            continue
        try:
            dt = parsedate_to_datetime(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue

    for key in ("published_parsed", "updated_parsed"):
        value = entry.get(key)
        if value:
            try:
                return datetime.fromtimestamp(time.mktime(value), tz=timezone.utc)
            except Exception:
                continue
    return None


def collect_recent_entries(
    feeds: list[dict[str, Any]],
    hours_back: int,
    sleep_seconds: float = 0.2,
) -> list[dict[str, Any]]:
    """
    Összegyűjti az összes feed friss bejegyzéseit.

    Duplikátumszűrés: (normalizált cím, link) pár alapján – azonos cikk
    több forrásban is megjelenhet (pl. Reuters + AP ugyanarról).

    Args:
        feeds:          A load_feeds() által visszaadott lista.
        hours_back:     Ennyi órára visszamenőleg gyűjtünk.
        sleep_seconds:  Várakozás feed-ek között (kíméletes terhelés).

    Returns:
        Időrendi sorrendben (legújabb elöl) rendezett bejegyzéslista.
        Minden elem dict a következő kulcsokkal:
        source, lang, country, category, title, link, published (ISO 8601 UTC), summary.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for feed in feeds:
        parsed = feedparser.parse(feed["rss"])
        for entry in getattr(parsed, "entries", []):
            dt = parse_entry_date(entry)
            if dt is None or dt < cutoff:
                continue

            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            if not title or not link:
                continue

            key = (normalize_title(title), link)
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "source": feed["name"],
                    "lang": feed["lang"],
                    "country": feed.get("country", ""),
                    "category": feed.get("category", "hirek"),
                    "title": title,
                    "link": link,
                    "published": dt.isoformat(),
                    "summary": entry.get("summary", ""),
                }
            )
        time.sleep(sleep_seconds)

    items.sort(key=lambda x: x["published"], reverse=True)
    return items
