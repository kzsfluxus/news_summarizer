from __future__ import annotations

from pathlib import Path


def build_news_markdown(items: list[dict], window: str) -> str:
    parts = [
        f"# Begyűjtött hírek ({window})",
        "",
        "Az alábbi tételek rövid, feldolgozott hírkivonatok.",
        "Az azonos eseményről szóló tételeket az összefoglalóban vond össze.",
        "",
    ]

    for idx, item in enumerate(items, start=1):
        title = item.get("title", "").strip()
        source = item.get("source", "").strip()
        published = item.get("published", "").strip()
        summary = item.get("mini_summary_hu", "").strip()

        parts.extend([
            f"## {idx}. {title}",
            f"Forrás: {source}",
            f"Dátum: {published}",
            "",
            "Kivonat:",
            summary,
            "",
            "---",
            "",
        ])

    return "\n".join(parts).strip() + "\n"


def save_markdown(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")