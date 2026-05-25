# Hírösszefoglaló

RSS-alapú hírgyűjtő, fordító és összefoglaló rendszer, lokális Ollama inferenciával,
GLiNER entitáskinyeréssel, KeyBERT kulcsszavazással és relevancia-rankinggal.

## Funkciók

- SQLite alapú helyi tárolás (sources, articles, article_keywords, article_entities, summaries, jobs)
- URL-szintű cache – már feldolgozott cikkek kihagyása
- Tartalom-hash alapú duplikátumszűrés (első 8 mondat SHA-256)
- Többnyelvű RSS feldolgozás: hu, en, de, fr
- Chunkolt fordítás magyarra (`deep-translator`)
- Extraktív mini-összefoglaló (első N mondat)
- GLiNER entitáskinyerés (PERSON, ORG, LOCATION, EVENT, PRODUCT)
- KeyBERT kulcsszókinyerés (paraphrase-multilingual-MiniLM-L12-v2)
- Relevancia-score ranking (forrásszám + frissesség + entitássúly + kulcsszósúly)
- Háttérszálas pipeline, job állapot SQLite-ban perzisztálva
- Automatikus Ollama subprocess kezelés (indítás és leállítás)
- Párhuzamos job indítás védelme

## Könyvtárstruktúra

```text
news_summarizer/
├── app.py                   # Flask belépési pont, API végpontok
├── config.py                # Minden hangolható konstans
├── feeds.yaml               # RSS források konfigurációja
├── prompt_builder.py        # Ollama system/user prompt összeállítás
├── requirements.txt
├── output/
│   ├── jobs/                # Megtartva visszafelé kompatibilitásból (üres)
│   ├── news.db              # SQLite adatbázis
│   ├── news.md              # Pipeline közbülső kimenete (Ollama bemenet)
│   └── summary.html         # Végső összefoglaló
├── services/
│   ├── __init__.py
│   ├── db_service.py        # Adatbázis-réteg
│   ├── feed_service.py      # RSS beolvasás, dátumnormalizálás
│   ├── scrape_service.py    # Cikk letöltés, szövegtisztítás, ujjlenyomat
│   ├── translate_service.py
│   ├── ner_service.py       # GLiNER entitáskinyerés
│   ├── keyword_service.py   # KeyBERT kulcsszókinyerés
│   ├── relevance_service.py # Relevancia-score számítás
│   ├── markdown_service.py  # news.md előállítása
│   ├── html_service.py      # Markdown → HTML konverzió
│   ├── ollama_service.py    # Ollama subprocess és inferencia
│   ├── job_service.py       # JobRegistry SQLite háttérrel
│   └── pipeline_service.py  # Fő feldolgozási pipeline
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

A GLiNER (~400 MB) és a KeyBERT sentence-transformer modell (~120 MB) az első
pipeline futáskor töltődnek le automatikusan a Hugging Face hub-ról.

## API végpontok

| Végpont | Metódus | Leírás |
|---|---|---|
| `/` | GET | Főoldal |
| `/run` | POST | Pipeline indítása `{"window": "24h"}` payloaddal |
| `/status/<job_id>` | GET | Job állapot lekérdezése |
| `/entities/<article_id>` | GET | Egy cikk entitásai |
| `/keywords/<article_id>` | GET | Egy cikk kulcsszavai |
| `/top-entities?window=24h` | GET | Leggyakoribb entitások az időablakban |
| `/top-keywords?window=24h` | GET | Leggyakoribb kulcsszavak az időablakban |

Időablak értékek: `12h`, `24h`, `7d`.

## Pipeline lépései

1. RSS feedek beolvasása és időablak szerinti szűrés
2. URL-cache ellenőrzés
3. Cikk scrape (trafilatura + requests fallback) és szövegtisztítás
4. Tartalom-hash duplikátumszűrés
5. Fordítás magyarra (nem-hu cikkek, chunkolt)
6. Extraktív mini-összefoglaló generálása
7. SQLite mentés
8. GLiNER entitáskinyerés (content_hu)
9. KeyBERT kulcsszókinyerés (content_hu)
10. Relevancia-score batch számítás az időablak összes cikkén
11. `news.md` előállítása relevancia szerint rendezve
12. Ollama inferencia (összefoglaló generálás)
13. HTML renderelés, mentés, job lezárása

## Relevancia-score

A score négy összetevőből áll (0.0–1.0):

| Összetevő | Súly | Leírás |
|---|---|---|
| Forrásszám | 35% | Hány különböző forrás ír hasonló témáról (kulcsszó-átfedés alapján) |
| Frissesség | 25% | Exponenciális bomlás, 12 órás felezési idővel |
| Entitássúly | 25% | Entitások száma × átlagos GLiNER konfidencia |
| Kulcsszósúly | 15% | Top-5 KeyBERT kulcsszó átlagos relevancia-értéke |

## Adatbázis séma

**sources** – RSS források (feeds.yaml tükre)

**articles** – Feldolgozott cikkek + `relevance_score` mező

**article_keywords** – KeyBERT kulcsszavak: article_id, keyword, score

**article_entities** – GLiNER entitások: article_id, entity_text, entity_type, score

**summaries** – Időablakos Ollama összefoglalók

**jobs** – Pipeline job állapotok

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
- A fordítás `deep-translator` alapú, API-kulcs nélkül
- A GLiNER magyar NER minősége korlátozott kevésbé ismert entitásoknál
- Nincs teljes szöveges keresés (4. fázis)
- Nincs témamodellezés (3. fázis)
