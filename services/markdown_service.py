"""
news.md előállítása az Ollama prompt számára.

A `build_news_markdown` függvény az adatbázisból lekért cikkek
`mini_summary_hu` mezőjéből strukturált Markdown dokumentumot épít.
Ez a dokumentum lesz az Ollama USER_TEMPLATE `{news_markdown}` paramétere.

A kimeneti formátum szándékosan egyszerű: sorszámozott cikkblokkok
forrás- és dátumjelöléssel, hogy az LLM könnyen azonosíthassa
az összetartozó híreket és összevonhassa a duplikátumokat.
"""

from __future__ import annotations

from pathlib import Path


def build_news_markdown(items: list[dict], window: str) -> str:
    """
    Felépíti a hírkivonat Markdown dokumentumot.

    Args:
        items:  Az adatbázisból lekért cikkek listája (list_articles_since kimenete).
        window: Az időablak azonosítója (csak a fejlécben jelenik meg).

    Returns:
        Markdown string, amelyet az ollama_service kap meg promptként.
    """
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
    """Elmenti a Markdown tartalmat a megadott útvonalra (UTF-8)."""
    path.write_text(content, encoding="utf-8")
