"""
Alkalmazásszintű konfiguráció.

Minden hangolható paramétert itt tárolunk; a service-ek innen importálnak,
nem tartalmaznak hard-coded értékeket.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Könyvtárstruktúra
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
JOBS_DIR = OUTPUT_DIR / "jobs"      # Megtartva visszafelé kompatibilitásból; az 1. fázis
                                    # óta a job-állapot SQLite-ban tárolódik, nem JSON fájlokban.
OUTPUT_DIR.mkdir(exist_ok=True)
JOBS_DIR.mkdir(exist_ok=True)

DB_PATH = OUTPUT_DIR / "news.db"            # SQLite adatbázis
NEWS_MD = OUTPUT_DIR / "news.md"            # Pipeline közbülső kimenete (Ollama bemenet)
SUMMARY_HTML = OUTPUT_DIR / "summary.html"  # Végső összefoglaló, iframe-ben jelenik meg
FEEDS_FILE = BASE_DIR / "feeds.yaml"        # RSS források konfigurációja

# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

OLLAMA_MODEL = "llama3.2:3b"                        # Helyi modell neve
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"  # Generálási végpont
OLLAMA_BASE_URL = "http://127.0.0.1:11434"          # Health check és modell-kezelés
OLLAMA_START_TIMEOUT = 30    # Másodperc: ennyi ideig várunk az `ollama serve` indulására
OLLAMA_WAIT_SECONDS = 0.5    # Poll intervallum a health check során

# ---------------------------------------------------------------------------
# Időablakok
# ---------------------------------------------------------------------------

# Kulcs: a frontend által küldött string érték; érték: órák száma
WINDOWS = {
    "12h": 12,
    "24h": 24,
    "7d": 24 * 7,
}

# ---------------------------------------------------------------------------
# Pipeline korlátok
# ---------------------------------------------------------------------------

REQUEST_TIMEOUT = 1200      # Ollama generálási timeout másodpercben (hosszú szövegnél lassú)
MAX_ENTRIES_PER_RUN = 30    # Legfeljebb ennyi RSS bejegyzést dolgozunk fel futásonként
MAX_SUMMARY_ITEMS = 14      # Legfeljebb ennyi cikket adunk át az Ollama promptnak
SCRAPE_DELAY_SECONDS = 0.3  # Várakozás feed-ek között (kíméletes terhelés)
MAX_ARTICLE_CHARS = 12000   # Cikk szövegének maximális hossza karakterben scrape után;
                            # ennél hosszabb szöveg csonkítva kerül tárolásra
MIN_ARTICLE_TEXT_LENGTH = 400   # Ennél rövidebb szöveg nem kerül feldolgozásra
                                # (pl. paywallok mögötti üres lapok kiszűrése)
TRANSLATION_CHUNK_SIZE = 3500   # GoogleTranslator API-korlát közelében (~5000 kar.);
                                # konzervatív érték, hogy szélső eseteket is kezelje
CONTEXT_TARGET_CHARS = 700      # A `context_hu` mező célhossza: rövidített változat,
                                # jelenleg nem kerül be az Ollama promptba –
                                # jövőbeli felhasználásra fenntartva
MINI_SUMMARY_SENTENCES = 5      # Extraktív mini-összefoglaló maximális mondatszáma;
                                # ez kerül be a news.md-be és az Ollama promptba

USER_AGENT = "Mozilla/5.0 news-summarizer/3.0"

# ---------------------------------------------------------------------------
# Ollama generálási beállítások
# ---------------------------------------------------------------------------

OLLAMA_TEMPERATURE = 0.2    # Alacsony hőmérséklet: determinisztikusabb, tényszerűbb kimenet
OLLAMA_NUM_PREDICT = 700    # Maximális generált tokenszám; 700 elegendő egy strukturált
                            # összefoglalóhoz – ha a kimenet csonkul, emelhető 1200-ra
OLLAMA_KEEP_ALIVE = 0       # Generálás után azonnal kirakja a modellt a memóriából;
                            # otthoni gépen előnyös, szerver környezetben 300-ra állítható
