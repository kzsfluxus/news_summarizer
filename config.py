"""
Alkalmazásszintű konfiguráció.

Minden hangolható paramétert itt tárolunk; a service-ek innen importálnak,
nem tartalmaznak hard-coded értékeket.

Ez a fájl MODELLFÜGGETLEN: a benne lévő alapértékek bármely Ollama-modellel
működnek. A modell-specifikus felülírásokat a `config_local.py` fájl végzi
(lásd a fájl alján lévő override-blokkot). Ha nincs `config_local.py`, az
alkalmazás a lenti alapértékekkel fut.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Könyvtárstruktúra
# ---------------------------------------------------------------------------

BASE_DIR   = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
JOBS_DIR   = OUTPUT_DIR / "jobs"      # Megtartva visszafelé kompatibilitásból (üres)
OUTPUT_DIR.mkdir(exist_ok=True)
JOBS_DIR.mkdir(exist_ok=True)

DB_PATH        = OUTPUT_DIR / "news.db"
NEWS_MD        = OUTPUT_DIR / "news.md"
SUMMARY_HTML   = OUTPUT_DIR / "summary.html"
NEWSLETTER_HTML = OUTPUT_DIR / "newsletter.html"   # Hírlevél kimenet (3. fázis)
FEEDS_FILE     = BASE_DIR / "feeds.yaml"

# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

OLLAMA_MODEL        = "llama3.2:3b"   # Alapértelmezett modell; config_local.py felülírhatja
OLLAMA_URL          = "http://127.0.0.1:11434/api/generate"
OLLAMA_BASE_URL     = "http://127.0.0.1:11434"
OLLAMA_START_TIMEOUT = 30
OLLAMA_WAIT_SECONDS  = 0.5

# ---------------------------------------------------------------------------
# Időablakok
# ---------------------------------------------------------------------------

WINDOWS = {
    "12h": 12,
    "24h": 24,
    "7d":  24 * 7,
}

# ---------------------------------------------------------------------------
# Pipeline korlátok
# ---------------------------------------------------------------------------

REQUEST_TIMEOUT          = 1200
MAX_ENTRIES_PER_RUN      = 30
MAX_SUMMARY_ITEMS        = 8          # Hány top-relevancia hír kerül az összefoglalóba
SCRAPE_DELAY_SECONDS     = 0.3
MAX_ARTICLE_CHARS        = 12000
MIN_ARTICLE_TEXT_LENGTH  = 400
TRANSLATION_CHUNK_SIZE   = 3500
CONTEXT_TARGET_CHARS     = 700
MINI_SUMMARY_SENTENCES   = 5

USER_AGENT = "Mozilla/5.0 news-summarizer/3.0"

# ---------------------------------------------------------------------------
# Ollama generálási beállítások
# ---------------------------------------------------------------------------
#
# Ezek univerzális Ollama-opciók: minden modell elfogadja őket.
# A num_ctx-et szándékosan EXPLICIT állítjuk (az Ollama alapértéke 4096, és
# csendben csonkolja az ennél hosszabb promptot). Így a kontextusablakot
# mi szabályozzuk, nem a rejtett alapérték.
#
# A sampling finomhangolása (top_p, top_k, repeat_penalty stb.) szándékosan
# NEM itt van, hanem a modell saját definíciójában (Modelfile) – így minden
# modell a hozzá illő mintavételezéssel fut, és az app-kód generikus marad.

OLLAMA_TEMPERATURE = 0.2
OLLAMA_NUM_PREDICT = 700
OLLAMA_NUM_CTX     = 4096   # Explicit alapérték; config_local.py felemelheti
OLLAMA_KEEP_ALIVE  = 0

# ---------------------------------------------------------------------------
# Lokális (modell-specifikus) felülírások
# ---------------------------------------------------------------------------
#
# Ha létezik egy `config_local.py` a config.py mellett, az itteni értékeket
# felülírja. Ide kerül minden, ami az adott modellhez / géphez kötött
# (pl. OLLAMA_MODEL = "racka-chat:latest", nagyobb num_ctx, több hír).
# Ha nincs ilyen fájl, az alkalmazás a fenti modellfüggetlen alapértékekkel fut.

try:
    from config_local import *  # noqa: F401,F403
except ImportError:
    pass
