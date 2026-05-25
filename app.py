"""
Flask alkalmazás belépési pontja.

Végpontok:
  GET  /                        – Főoldal (index.html)
  POST /run                     – Pipeline job indítása; futó job esetén
                                  visszaadja az aktív job ID-ját
  GET  /status/<id>             – Job állapot lekérdezése
  GET  /entities/<article_id>   – Egy cikk entitásai
  GET  /top-entities            – Legtöbbször előforduló entitások az
                                  időablakban (?window=24h, alapértelmezett)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, render_template, request

from config import WINDOWS
from services.db_service import get_entities_for_article, get_top_entities_since, init_db
from services.pipeline_service import registry, start_job

app = Flask(__name__)
init_db()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/run", methods=["POST"])
def run_job():
    active = registry.active_job()
    if active:
        return jsonify({"ok": True, "job_id": active.job_id, "already_running": True})

    payload = request.get_json(silent=True) or {}
    window = payload.get("window", "24h")
    job_id = start_job(window)
    return jsonify({"ok": True, "job_id": job_id, "already_running": False})


@app.route("/status/<job_id>")
def status(job_id: str):
    job = registry.get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Ismeretlen job_id"}), 404
    return jsonify(job.to_dict())


@app.route("/entities/<int:article_id>")
def entities(article_id: int):
    """Visszaadja egy cikk entitásait score szerint csökkenő sorrendben."""
    return jsonify(get_entities_for_article(article_id))


@app.route("/top-entities")
def top_entities():
    """
    Visszaadja a leggyakrabban előforduló entitásokat az időablakban.
    Query paraméter: ?window=24h (alapértelmezett), 12h, 7d
    """
    window = request.args.get("window", "24h")
    hours_back = WINDOWS.get(window, 24)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()
    return jsonify(get_top_entities_since(cutoff, limit=30))


if __name__ == "__main__":
    app.run(debug=True)
