"""
Hírlevél HTML kimenet generálása.

A hírlevél témák szerint szervezett, önálló HTML fájl,
amelyet e-mailben is el lehet küldeni vagy böngészőben meg lehet nyitni.

Felépítés:
  - Fejléc: dátum, időablak, statisztikák
  - Témacsoportok: minden témához a legfontosabb cikkek
    (relevancia szerint rendezve, mini-összefoglalóval)
  - Lábléc: forráslistával

A HTML inline CSS-t használ, hogy e-mail kliensekben is megfelelően
jelenjen meg (nem támaszkodik külső stylesheetekre).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def _escape(text: str) -> str:
    """Minimális HTML escape; elegendő a cikkcímek és összefoglalók biztonságos megjelenítéséhez."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


def build_newsletter(
    topics: list[dict],
    articles: list[dict],
    topic_ids: list[int],
    window: str,
) -> str:
    """
    Összeállítja a hírlevél HTML-t.

    Args:
        topics:    A compute_topics() által visszaadott témák listája
                   (label, keywords, article_count, trend_score).
        articles:  Az időablakon belüli cikkek listája topics mezővel.
        topic_ids: A topics táblába mentett DB id-k (azonos sorrendben mint topics).
        window:    Időablak azonosítója (megjelenítéshez).

    Returns:
        Teljes HTML string.
    """
    now_str = datetime.now(timezone.utc).strftime("%Y. %m. %d. %H:%M UTC")
    total_articles = len(articles)
    total_sources = len({a.get("source", "") for a in articles})

    # Téma → cikkek mapping DB topic_id alapján
    topic_articles: dict[int, list[dict]] = {tid: [] for tid in topic_ids}
    for article in articles:
        for at in article.get("topics", []):
            tid = at.get("id")
            if tid in topic_articles:
                topic_articles[tid].append((at.get("similarity", 0.0), article))

    # Cikkeket relevancia + similarity alapján rendezzük
    for tid in topic_articles:
        topic_articles[tid].sort(
            key=lambda x: x[0] * 0.4 + x[1].get("relevance_score", 0.0) * 0.6,
            reverse=True,
        )

    sections_html = ""
    for topic, tid in zip(topics, topic_ids):
        art_list = topic_articles.get(tid, [])
        if not art_list:
            continue

        articles_html = ""
        for sim, art in art_list[:4]:  # Témánként max 4 cikk
            title = _escape(art.get("title", ""))
            source = _escape(art.get("source", ""))
            pub = art.get("published", "")[:10]
            summary = _escape(art.get("mini_summary_hu", ""))
            url = art.get("url", "#")
            rel = int(art.get("relevance_score", 0.0) * 100)
            kw_list = [kw["keyword"] for kw in art.get("keywords", [])[:5]]
            kw_html = "".join(
                f'<span style="display:inline-block;padding:2px 8px;margin:2px;'
                f'background:#1e3a5f;border-radius:999px;font-size:11px;color:#93c5fd">'
                f'{_escape(k)}</span>'
                for k in kw_list
            )
            articles_html += f"""
            <div style="border:1px solid #334155;border-radius:10px;padding:14px;
                        margin-bottom:10px;background:#111827">
              <div style="display:flex;justify-content:space-between;
                          align-items:flex-start;margin-bottom:6px">
                <a href="{url}" style="color:#93c5fd;font-weight:600;
                                       font-size:15px;text-decoration:none">
                  {title}
                </a>
                <span style="font-size:11px;color:#64748b;white-space:nowrap;
                             margin-left:8px">{rel}% rel.</span>
              </div>
              <div style="font-size:12px;color:#64748b;margin-bottom:6px">
                {source} · {pub}
              </div>
              <p style="font-size:13px;color:#cbd5e1;margin:0 0 8px">{summary}</p>
              <div>{kw_html}</div>
            </div>
            """

        trend_pct = int(min(topic.get("trend_score", 0.0) * 100, 100))
        sections_html += f"""
        <div style="margin-bottom:28px">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
            <h2 style="margin:0;font-size:17px;color:#f1f5f9">
              {_escape(topic['label'])}
            </h2>
            <span style="font-size:11px;color:#94a3b8;background:#1e293b;
                         padding:2px 8px;border-radius:999px">
              {topic['article_count']} cikk · trend {trend_pct}%
            </span>
          </div>
          <div style="font-size:12px;color:#64748b;margin-bottom:10px">
            Kulcsszavak: {_escape(topic['keywords'])}
          </div>
          {articles_html}
        </div>
        """

    # Forrás lista
    sources = sorted({a.get("source", "") for a in articles if a.get("source")})
    sources_html = " · ".join(_escape(s) for s in sources)

    html = f"""<!doctype html>
<html lang="hu">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Hírösszefoglaló – {_escape(window)}</title>
</head>
<body style="font-family:Inter,system-ui,sans-serif;background:#0f172a;
             color:#e5e7eb;max-width:740px;margin:0 auto;padding:24px 16px 48px">

  <div style="border-bottom:1px solid #334155;padding-bottom:16px;margin-bottom:24px">
    <h1 style="margin:0 0 4px;font-size:22px;color:#f8fafc">
      📰 Hírösszefoglaló
    </h1>
    <div style="font-size:13px;color:#64748b">
      {now_str} · Időablak: {_escape(window)} ·
      {total_articles} cikk · {total_sources} forrás ·
      {len(topics)} téma
    </div>
  </div>

  {sections_html}

  <div style="border-top:1px solid #334155;padding-top:14px;
              font-size:11px;color:#475569;margin-top:8px">
    Források: {sources_html}
  </div>

</body>
</html>
"""
    return html


def save_newsletter(path: Path, html: str) -> None:
    """Elmenti a hírlevél HTML-t a megadott útvonalra (UTF-8)."""
    path.write_text(html, encoding="utf-8")
