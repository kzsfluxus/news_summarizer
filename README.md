# Hírösszefoglaló

RSS-alapú hírgyűjtő, fordító és összefoglaló rendszer, lokális Ollama inferenciával és GLiNER entitáskinyeréssel.

## Funkciók

- SQLite alapú helyi tárolás (sources, articles, article_entities, summaries, jobs)
- URL-szintű cache – már feldolgozott cikkek kihagyása
- Tartalom-hash alapú duplikátumszűrés (első 8 mondat SHA-256)
- Többnyelvű RSS feldolgozás: hu, en, de, fr
- Chunkolt fordítás magyarra (`deep-translator`)
- Extraktív mini-összefoglaló (első N mondat)
- GLiNER alapú entitáskinyerés (személy, szervezet, helyszín, esemény, termék)
- Háttérszálas pipeline, job állapot SQLite-ban perzisztálva
- Automatikus Ollama subprocess kezelés (indítás és leállítás)
- Párhuzamos job indítás védelme
- `news.md`, `summary.html`, `news.db` kimenetek

## Könyvtárstruktúra

```text
news_summarizer/
├── app.py                  # Flask belépési pont, API végpontok
├── config.py               # Minden hangolható konstans
├── feeds.yaml              # RSS források konfigurációja
├── prompt_builder.py       # Ollama system/user prompt összeállítás
├── requirements.txt
├── output/
│   ├── jobs/               # Megtartva visszafelé kompatibilitásból (üres)
│   ├── news.db             # SQLite adatbázis
│   ├── news.md             # Pipeline közbülső kimenete (Ollama bemenet)
│   └── summary.html        # Végső összefoglaló
├── services/
│   ├── __init__.py
│   ├── db_service.py       # Adatbázis-réteg
│   ├── feed_service.py     # RSS beolvasás, dátumnormalizálás
│   ├── scrape_service.py   # Cikk letöltés, szövegtisztítás, ujjlenyomat
│   ├── translate_service.py
│   ├── ner_service.py      # GLiNER entitáskinyerés
│   ├── markdown_service.py # news.md előállítása
│   ├── html_service.py     # Markdown → HTML konverzió
│   ├── ollama_service.py   # Ollama subprocess és inferencia
│   ├── job_service.py      # JobRegistry SQLite háttérrel
│   └── pipeline_service.py # Fő feldolgozási pipeline
├── static/
│   └── app.js
└── templates/
    └── index.html
```

## Indítás

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

A felület: `http://127.0.0.1:5000`

Az Ollama modell szükséges (ha még nincs letöltve):

```bash
ollama pull llama3.2:3b
```

A GLiNER modell (~400 MB) az első pipeline futáskor töltődik le automatikusan a Hugging Face hub-ról.

## API végpontok

| Végpont | Metódus | Leírás |
|---|---|---|
| `/` | GET | Főoldal |
| `/run` | POST | Pipeline indítása `{"window": "24h"}` payloaddal |
| `/status/<job_id>` | GET | Job állapot lekérdezése |
| `/entities/<article_id>` | GET | Egy cikk entitásai |
| `/top-entities?window=24h` | GET | Leggyakoribb entitások az időablakban |

Időablak értékek: `12h`, `24h`, `7d`.

## Pipeline lépései

1. RSS feedek beolvasása és időablak szerinti szűrés
2. URL-cache ellenőrzés (már feldolgozott cikkek kihagyása)
3. Cikk scrape (trafilatura + requests fallback), szövegtisztítás
4. Tartalom-hash duplikátumszűrés
5. Fordítás magyarra (nem-hu cikkek esetén, chunkolt)
6. Extraktív mini-összefoglaló generálása
7. SQLite mentés
8. GLiNER entitáskinyerés a teljes magyar szövegen
9. `news.md` előállítása az Ollama prompthoz
10. Ollama inferencia (összefoglaló generálás)
11. HTML renderelés, mentés, job lezárása

## Ollama kezelés

- Ha az Ollama már fut a `127.0.0.1:11434` címen, a program azt használja
- Ha nem fut, elindítja `ollama serve` paranccsal
- A feldolgozás végén csak akkor állítja le, ha ő indította el
- A modell a válasz után azonnal kikerül a memóriából (`keep_alive: 0`)

## Adatbázis séma

A `news.db` SQLite adatbázis táblái:

**sources** – RSS források (feeds.yaml tükre, pipeline indulásakor szinkronizálva)

**articles** – Feldolgozott cikkek: url, title, source, lang, country, category, published, scraped_at, content (eredeti), content_hu (fordított), content_hash, mini_summary_hu

**article_entities** – NER entitások: article_id, entity_text, entity_type (PERSON / ORG / LOCATION / EVENT / PRODUCT), score

**summaries** – Időablakos Ollama összefoglalók: window, created_at, content_md, html, source_count

**jobs** – Pipeline job állapotok: job_id, stage, progress, message, html, error, stats (JSON), created_at, updated_at

## Konfigurációs paraméterek (config.py)

| Paraméter | Alapértelmezett | Leírás |
|---|---|---|
| `OLLAMA_MODEL` | `llama3.2:3b` | Helyi Ollama modell |
| `MAX_ENTRIES_PER_RUN` | `30` | RSS bejegyzések feldolgozási korlátja |
| `MAX_SUMMARY_ITEMS` | `14` | Ollama promptba kerülő cikkek száma |
| `MAX_ARTICLE_CHARS` | `12000` | Cikkszöveg karakterkorlátja |
| `MIN_ARTICLE_TEXT_LENGTH` | `400` | Rövidebb szöveg nem kerül feldolgozásra |
| `OLLAMA_NUM_PREDICT` | `700` | Generált tokenek maximuma |
| `OLLAMA_TEMPERATURE` | `0.2` | Alacsony = determinisztikusabb kimenet |

## Korlátok

- A mini-összefoglaló extraktív (első N mondat), nem absztraktív
- A fordítás `deep-translator` (Google Translate) alapú, API-kulcs nélkül
- A GLiNER magyar NER minősége korlátozott kevésbé ismert entitásoknál
- Nincs témaszűrés vagy relevancia-ranking (2. fázis fennmaradó feladata)
- Nincs teljes szöveges keresés (4. fázis)
