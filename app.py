"""
Flask alkalmazás belépési pontja.

Végpontok:
  GET  /              – Főoldal (index.html)
  POST /run           – Új pipeline job indítása; ha már fut egy job,
                        visszaadja annak ID-ját (already_running: true)
  GET  /status/<id>   – Job állapotának lekérdezése (stage, progress, stats, html)

A pipeline háttérszálban fut; az állapot SQLite-ban tárolódik és
a frontend 1,2 másodpercenként lekérdezi.
"""

from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from services.db_service import init_db
from services.pipeline_service import registry, start_job

app = Flask(__name__)
init_db()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/run", methods=["POST"])
def run_job():
    # Ha már fut egy job, visszaadjuk annak ID-ját, nem indítunk újat
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


if __name__ == "__main__":
    app.run(debug=True)
