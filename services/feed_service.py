from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import time
import re
from typing import Any

import feedparser
import yaml

SPACE_RE = re.compile(r"\s+")


def normalize_title(value: str) -> str:
    return SPACE_RE.sub(" ", (value or "").strip().lower())


def load_feeds(path: str) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("feeds", [])


def parse_entry_date(entry) -> datetime | None:
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


def collect_recent_entries(feeds: list[dict[str, Any]], hours_back: int, sleep_seconds: float = 0.2) -> list[dict[str, Any]]:
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
