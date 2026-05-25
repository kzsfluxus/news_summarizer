"""
Fő feldolgozási pipeline.

Pipeline lépések:
  1.  RSS → bejegyzések begyűjtése
  2.  URL-cache ellenőrzés
  3.  Scrape + szövegtisztítás
  4.  Tartalom-hash duplikátumszűrés
  5.  Fordítás magyarra
  6.  Extraktív mini-összefoglaló
  7.  SQLite mentés
  8.  GLiNER entitáskinyerés (content_hu)
  9.  KeyBERT kulcsszókinyerés (content_hu)
  10. Relevancia-score számítás (batch, az időablak összes cikkén)
  11. news.md előállítása (relevancia szerint rendezve)
  12. Ollama inferencia
  13. HTML renderelés és mentés

A 8-9. lépés hibája nem fatális: a pipeline folytatódik,
az érintett cikk entitás/kulcsszó nélkül kerül az összefoglalóba.

A relevancia-score (10. lépés) batch-ben fut az időablakon belüli
összes cikken – így a source_score a cache-elt régebbi cikkeket is
figyelembe veszi, nem csak az éppen scrape-elteket.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from threading import Thread
from typing import Any

from config import (
    CONTEXT_TARGET_CHARS,
    FEEDS_FILE,
    MAX_ARTICLE_CHARS,
    MAX_ENTRIES_PER_RUN,
    MAX_SUMMARY_ITEMS,
    MIN_ARTICLE_TEXT_LENGTH,
    MINI_SUMMARY_SENTENCES,
    NEWS_MD,
    OLLAMA_MODEL,
    OLLAMA_URL,
    SCRAPE_DELAY_SECONDS,
    SUMMARY_HTML,
    TRANSLATION_CHUNK_SIZE,
    WINDOWS,
)
from prompt_builder import build_prompt
from services.db_service import (
    article_exists,
    get_article_id,
    hash_exists,
    list_articles_since,
    save_article,
    save_entities,
    save_keywords,
    save_summary,
    sync_sources,
    update_relevance_score,
)
from services.feed_service import collect_recent_entries, load_feeds
from services.html_service import markdown_to_html
from services.job_service import JobRegistry
from services.keyword_service import extract_keywords
from services.markdown_service import build_news_markdown, save_markdown
from services.ner_service import extract_entities
from services.ollama_service import ensure_ollama, run_ollama, stop_ollama, unload_model
from services.relevance_service import compute_and_update_batch
from services.scrape_service import (
    ScrapeError,
    extract_main_text,
    extractive_mini_summary,
    fingerprint_text,
    shorten_for_context,
)
from services.translate_service import maybe_translate

registry = JobRegistry()


def _update(
    job_id: str,
    stage: str,
    progress: int,
    message: str,
    stats: dict[str, Any] | None = None,
) -> None:
    registry.update(job_id, stage=stage, progress=progress, message=message, stats=stats or {})


def _run_pipeline(job_id: str, window: str) -> None:
    stats: dict[str, Any] = {
        "rss_count": 0,
        "new_urls": 0,
        "cache_hits": 0,
        "scraped_ok": 0,
        "duplicates_removed": 0,
        "used_for_summary": 0,
        "scrape_errors": 0,
        "translation_count": 0,
        "ner_ok": 0,
        "ner_errors": 0,
        "keyword_ok": 0,
        "keyword_errors": 0,
        "lang_stats": {},
    }
    ollama_proc = None

    try:
        hours_back = WINDOWS.get(window, 24)
        feeds = load_feeds(str(FEEDS_FILE))
        sync_sources(feeds)

        # 1. RSS beolvasás
        _update(job_id, "rss", 5, "RSS feedek beolvasása", stats)
        entries = collect_recent_entries(feeds, hours_back, sleep_seconds=SCRAPE_DELAY_SECONDS)
        stats["rss_count"] = len(entries)

        # 2. URL-cache szűrés
        fresh_entries = []
        for entry in entries[:MAX_ENTRIES_PER_RUN]:
            if article_exists(entry["link"]):
                stats["cache_hits"] += 1
            else:
                fresh_entries.append(entry)
        stats["new_urls"] = len(fresh_entries)

        total = max(len(fresh_entries), 1)
        lang_counter: Counter = Counter()
        processed = []

        # 3–7. Scrape, fordítás, mentés
        for i, item in enumerate(fresh_entries, start=1):
            pct = 10 + int((i / total) * 30)
            _update(job_id, "scrape", pct, f"Cikkek feldolgozása: {i}/{len(fresh_entries)}", stats)

            try:
                text = extract_main_text(item["link"])
            except (ScrapeError, Exception):
                stats["scrape_errors"] += 1
                continue

            if len(text) < MIN_ARTICLE_TEXT_LENGTH:
                stats["scrape_errors"] += 1
                continue

            text = text[:MAX_ARTICLE_CHARS]
            content_hash = fingerprint_text(text)
            if hash_exists(content_hash):
                stats["duplicates_removed"] += 1
                continue

            text_hu = maybe_translate(text, item["lang"], chunk_size=TRANSLATION_CHUNK_SIZE)
            if item["lang"] != "hu":
                stats["translation_count"] += 1

            mini_summary = extractive_mini_summary(text_hu, max_sentences=MINI_SUMMARY_SENTENCES)
            item["clean_text"] = text
            item["clean_text_hu"] = text_hu
            item["mini_summary_hu"] = mini_summary
            item["context_hu"] = shorten_for_context(text_hu, target_chars=CONTEXT_TARGET_CHARS)
            item["content_hash"] = content_hash
            save_article(item)
            processed.append(item)
            stats["scraped_ok"] += 1
            lang_counter[item["lang"]] += 1

        stats["lang_stats"] = dict(lang_counter)

        # 8. GLiNER entitáskinyerés
        if processed:
            ner_total = len(processed)
            for j, item in enumerate(processed, start=1):
                pct = 40 + int((j / ner_total) * 15)
                _update(job_id, "ner", pct, f"Entitáskinyerés: {j}/{ner_total}", stats)
                article_id = get_article_id(item["link"])
                if article_id is None:
                    stats["ner_errors"] += 1
                    continue
                try:
                    entities = extract_entities(item["clean_text_hu"])
                    if entities:
                        save_entities(article_id, entities)
                    stats["ner_ok"] += 1
                except Exception:
                    stats["ner_errors"] += 1

        # 9. KeyBERT kulcsszókinyerés
        if processed:
            kw_total = len(processed)
            for j, item in enumerate(processed, start=1):
                pct = 55 + int((j / kw_total) * 15)
                _update(job_id, "keywords", pct, f"Kulcsszókinyerés: {j}/{kw_total}", stats)
                article_id = get_article_id(item["link"])
                if article_id is None:
                    stats["keyword_errors"] += 1
                    continue
                try:
                    keywords = extract_keywords(item["clean_text_hu"])
                    if keywords:
                        save_keywords(article_id, keywords)
                    stats["keyword_ok"] += 1
                except Exception:
                    stats["keyword_errors"] += 1

        # 10. Relevancia-score batch számítás az időablak összes cikkén
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()
        context_items = list_articles_since(cutoff_iso=cutoff, limit=MAX_SUMMARY_ITEMS * 3)

        _update(job_id, "relevance", 72, "Relevancia-score számítása", stats)
        scored_items = compute_and_update_batch(context_items)
        for article in scored_items:
            update_relevance_score(article["id"], article["relevance_score"])

        # Az Ollama prompthoz a relevancia szerint rendezett top cikkek mennek
        context_items = sorted(scored_items, key=lambda x: x["relevance_score"], reverse=True)
        context_items = context_items[:MAX_SUMMARY_ITEMS]
        stats["used_for_summary"] = len(context_items)

        if not context_items:
            html = "<p>Nincs feldolgozható cikk ebben az időablakban.</p>"
            SUMMARY_HTML.write_text(html, encoding="utf-8")
            registry.update(
                job_id, stage="done", progress=100,
                message="Nincs feldolgozható cikk", html=html, stats=stats,
            )
            return

        # 11. news.md
        _update(job_id, "markdown", 78, "news.md előállítása", stats)
        news_markdown = build_news_markdown(context_items, window)
        save_markdown(NEWS_MD, news_markdown)

        # 12. Ollama inferencia
        _update(job_id, "ollama", 85, "Ollama ellenőrzése / indítása", stats)
        ollama_proc = ensure_ollama()
        prompt = build_prompt(news_markdown, window)
        summary_md = run_ollama(prompt, model=OLLAMA_MODEL, url=OLLAMA_URL)

        if not summary_md or not summary_md.strip():
            raise RuntimeError("Az Ollama üres választ adott vissza.")

        # 13. HTML renderelés
        _update(job_id, "html", 95, "HTML előállítása", stats)
        html = markdown_to_html(summary_md)
        SUMMARY_HTML.write_text(html, encoding="utf-8")
        save_summary(window=window, content_md=summary_md, html=html, source_count=len(context_items))

        registry.update(
            job_id, stage="done", progress=100, message="Kész", html=html, stats=stats,
        )

    except Exception as exc:
        registry.update(
            job_id, stage="error", progress=100,
            message="Hiba történt", error=str(exc), stats=stats,
        )
    finally:
        unload_model()
        stop_ollama(ollama_proc)


def start_job(window: str) -> str:
    """
    Létrehoz egy új jobot és háttérszálban elindítja a pipeline-t.

    Args:
        window: Időablak azonosítója ("12h", "24h", "7d").

    Returns:
        Az új job UUID-je (hex string).
    """
    job = registry.create()
    thread = Thread(target=_run_pipeline, args=(job.job_id, window), daemon=True)
    thread.start()
    return job.job_id
