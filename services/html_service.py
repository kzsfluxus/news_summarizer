"""
Markdown → HTML konverzió az összefoglaló megjelenítéséhez.

A `markdown_to_html` függvény az Ollama által generált Markdown szöveget
önálló HTML oldallá alakítja, amelyet a frontend iframe-ben jelenít meg.

Biztonsági megjegyzések:
- `html: False` – raw HTML blokkok nem kerülnek a kimenetbe (XSS-védelem)
- `linkify: True` – bare URL-ek automatikusan linkké válnak
- A CSS változókon (CSS custom properties) alapul; sötét téma (dark mode)
"""

from __future__ import annotations

from markdown_it import MarkdownIt

# Az összefoglaló önálló HTML oldala; az __BODY__ placeholder helyére
# kerül a renderelt Markdown tartalom.
HTML_TEMPLATE = """<!doctype html>
<html lang="hu">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hírösszefoglaló</title>
  <style>
    :root {
      --bg: #0f172a;
      --card: #111827;
      --muted: #cbd5e1;
      --text: #e5e7eb;
      --border: #334155;
      --link: #93c5fd;
      --code: #1e293b;
    }
    body {
      font-family: Inter, system-ui, sans-serif;
      max-width: 920px;
      margin: 2rem auto;
      padding: 0 1rem 3rem;
      background: var(--bg);
      color: var(--text);
      line-height: 1.75;
    }
    article {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 1.5rem;
      box-shadow: 0 12px 32px rgba(0,0,0,0.18);
    }
    h1, h2, h3 { color: white; }
    h1 { border-bottom: 1px solid var(--border); padding-bottom: .75rem; }
    a { color: var(--link); }
    code { background: var(--code); padding: 0.15rem 0.35rem; border-radius: 6px; }
    pre { background: var(--code); padding: 1rem; border-radius: 12px; overflow-x: auto; }
    blockquote { border-left: 4px solid var(--border); padding-left: 1rem; color: var(--muted); }
    hr { border: 0; border-top: 1px solid var(--border); }
    ul, ol { padding-left: 1.35rem; }
  </style>
</head>
<body>
<article>__BODY__</article>
</body>
</html>
"""


def markdown_to_html(md_text: str) -> str:
    """
    Markdown szöveget teljes HTML oldallá alakít.

    Args:
        md_text: Az Ollama által generált Markdown összefoglaló.

    Returns:
        Önálló HTML oldal string, beágyazott CSS-sel.
    """
    md = MarkdownIt("commonmark", {"html": False, "linkify": True, "typographer": True})
    body = md.render(md_text)
    return HTML_TEMPLATE.replace("__BODY__", body)
