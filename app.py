"""
Flask alkalmazás belépési pontja.

Oldalak:
  GET  /                  – Főoldal (pipeline + NLP panelek)
  GET  /search            – Keresőoldal
  GET  /article/<id>      – Cikkoldal
  GET  /browse            – Témaböngésző
  GET  /admin             – Admin panel (sources, job előzmények, DB statisztikák)

API végpontok:
  POST /run                      – Pipeline indítása
  GET  /status/<job_id>          – Job állapot
  GET  /api/search               – JSON keresési eredmények
  GET  /api/entities/<id>        – Egy cikk entitásai
  GET  /api/keywords/<id>        – Egy cikk kulcsszavai
  GET  /api/top-entities         – Leggyakoribb entitások (?window=24h)
  GET  /api/top-keywords         – Leggyakoribb kulcsszavak (?window=24h)
  GET  /api/topics               – Aktuális témák (?window=24h)
  GET  /api/topic/<id>           – Egy téma részletei
  GET  /newsletter               – Hírlevél HTML
"""

from __future__ import annotations

import os
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, render_template, request, send_file

from config import NEWSLETTER_HTML, WINDOWS
from services.db_service import (
    get_article_by_id,
    get_db_stats,
    get_entities_for_article,
    get_keywords_for_article,
    get_topic_by_id,
    get_top_entities_since,
    get_top_keywords_since,
    get_topics_since,
    init_db,
    list_all_topics,
    list_distinct_entities,
    list_recent_jobs,
    list_sources,
)
from services.pipeline_service import registry, start_job
from services.search_service import run_search

app = Flask(__name__)
init_db()


# ---------------------------------------------------------------------------
# Oldalak
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/search")
def search_page():
    q        = request.args.get("q", "").strip()
    source   = request.args.get("source") or None
    date_from = request.args.get("from") or None
    date_to   = request.args.get("to") or None
    entity   = request.args.get("entity") or None
    topic_id = request.args.get("topic_id", type=int)
    page     = request.args.get("page", 1, type=int)

    results = {}
    if q:
        results = run_search(
            query=q, source=source, date_from=date_from,
            date_to=date_to, entity=entity, topic_id=topic_id,
            page=page,
        )

    sources  = list_sources()
    entities = list_distinct_entities(limit=100)
    topics   = list_all_topics(limit=50)

    return render_template(
        "search.html",
        q=q, results=results, sources=sources,
        entities=entities, topics=topics,
        source=source, date_from=date_from, date_to=date_to,
        entity=entity, topic_id=topic_id, page=page,
    )


@app.route("/article/<int:article_id>")
def article_page(article_id: int):
    article = get_article_by_id(article_id)
    if not article:
        return render_template("404.html"), 404
    return render_template("article.html", article=article)


@app.route("/browse")
def browse_page():
    window     = request.args.get("window", "24h")
    hours_back = WINDOWS.get(window, 24)
    cutoff     = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()
    topics     = get_topics_since(cutoff)
    return render_template("browse.html", topics=topics, window=window, windows=WINDOWS)


@app.route("/admin")
def admin_page():
    sources = list_sources()
    jobs    = list_recent_jobs(limit=20)
    stats   = get_db_stats()
    return render_template("admin.html", sources=sources, jobs=jobs, stats=stats)


# ---------------------------------------------------------------------------
# Pipeline API
# ---------------------------------------------------------------------------

@app.route("/run", methods=["POST"])
def run_job():
    active = registry.active_job()
    if active:
        return jsonify({"ok": True, "job_id": active.job_id, "already_running": True})
    payload = request.get_json(silent=True) or {}
    window  = payload.get("window", "24h")
    job_id  = start_job(window)
    return jsonify({"ok": True, "job_id": job_id, "already_running": False})


@app.route("/status/<job_id>")
def status(job_id: str):
    job = registry.get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Ismeretlen job_id"}), 404
    return jsonify(job.to_dict())


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------

@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "q paraméter kötelező"}), 400
    return jsonify(run_search(
        query=q,
        source=request.args.get("source") or None,
        date_from=request.args.get("from") or None,
        date_to=request.args.get("to") or None,
        entity=request.args.get("entity") or None,
        topic_id=request.args.get("topic_id", type=int),
        page=request.args.get("page", 1, type=int),
    ))


@app.route("/api/entities/<int:article_id>")
def api_entities(article_id: int):
    return jsonify(get_entities_for_article(article_id))


@app.route("/api/keywords/<int:article_id>")
def api_keywords(article_id: int):
    return jsonify(get_keywords_for_article(article_id))


@app.route("/api/top-entities")
def api_top_entities():
    window = request.args.get("window", "24h")
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=WINDOWS.get(window, 24))).isoformat()
    return jsonify(get_top_entities_since(cutoff, limit=30))


@app.route("/api/top-keywords")
def api_top_keywords():
    window = request.args.get("window", "24h")
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=WINDOWS.get(window, 24))).isoformat()
    return jsonify(get_top_keywords_since(cutoff, limit=40))


@app.route("/api/topics")
def api_topics():
    window = request.args.get("window", "24h")
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=WINDOWS.get(window, 24))).isoformat()
    return jsonify(get_topics_since(cutoff))


@app.route("/api/topic/<int:topic_id>")
def api_topic(topic_id: int):
    topic = get_topic_by_id(topic_id)
    if not topic:
        return jsonify({"error": "Nem található"}), 404
    return jsonify(topic)


@app.route("/newsletter")
def newsletter():
    if not NEWSLETTER_HTML.exists():
        return "<p>Még nem készült hírlevél.</p>", 404
    return send_file(NEWSLETTER_HTML, mimetype="text/html")


if __name__ == "__main__":
    app.run(debug=True)
