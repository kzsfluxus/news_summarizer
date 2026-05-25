# Hírösszefoglaló

RSS-alapú hírgyűjtő, fordító és összefoglaló rendszer, lokális Ollama inferenciával,
GLiNER entitáskinyeréssel, KeyBERT kulcsszavazással, TF-IDF témamodellezéssel,
FTS5 teljes szöveges kereséssel és hírlevél-generálással.

## Gépigény

### Minimális konfiguráció

| Összetevő | Minimum |
|---|---|
| CPU | 4 mag, 2.0 GHz+ |
| RAM | 8 GB |
| Tárhely | 5 GB (modellek + adatbázis) |
| OS | Linux (Debian 11+, Ubuntu 22.04+), macOS 12+ |

A minimális konfiguráción az Ollama CPU-n fut (~3–8 perc/összefoglaló),
a GLiNER és KeyBERT modellek egymás után töltődnek be (~2–5 perc az első futáskor).
Az NLP lépések (NER + kulcsszavazás) 30 cikkre ~5–10 perc.

### Ajánlott konfiguráció

| Összetevő | Ajánlott |
|---|---|
| CPU | 8 mag, 3.0 GHz+ |
| RAM | 16 GB |
| GPU | NVIDIA 8 GB VRAM (RTX 3060 vagy jobb) |
| Tárhely | 10 GB |
| OS | Linux |

GPU jelenlétében az Ollama inferencia ~10–30 másodperc, az NLP lépések
(GLiNER, KeyBERT) 2–5× gyorsabbak. A `sentence-transformers` és a `gliner`
automatikusan felismeri a CUDA/MPS eszközt.

## Függőségek

### Ollama (helyi LLM inferencia)

Az Ollama szükséges a szövegösszefoglaláshoz. Telepítési útmutató:
**https://ollama.com/download**

A pipeline automatikusan elindítja az Ollama szervert, ha még nem fut,
és leállítja, ha ő indította el.

Szükséges modell (első futás előtt):

```bash
ollama pull llama3.2:3b
```

A modell mérete ~2 GB. CPU-n is fut, GPU-val lényegesen gyorsabb.
Alternatívaként a `config.py`-ban bármely Ollama-kompatibilis modell megadható.

### Python függőségek

A modellek az első pipeline futáskor töltődnek le automatikusan
a Hugging Face hub-ról (internet-hozzáférés szükséges):

| Csomag | Modell | Méret | Feladat |
|---|---|---|---|
| `gliner` | `urchade/gliner_multi-v2.1` | ~400 MB | NER entitáskinyerés |
| `sentence-transformers` | `paraphrase-multilingual-MiniLM-L12-v2` | ~120 MB | KeyBERT kulcsszavazás |

A TF-IDF témamodellezés és az FTS5 keresés offline, külön modell nélkül működik.

## Funkciók

- SQLite alapú helyi tárolás (8 tábla, FTS5 virtuális tábla)
- URL-szintű cache és tartalom-hash duplikátumszűrés
- Többnyelvű RSS feldolgozás: hu, en, de, fr
- Chunkolt fordítás magyarra (`deep-translator`)
- GLiNER entitáskinyerés (PERSON, ORG, LOCATION, EVENT, PRODUCT)
- KeyBERT kulcsszókinyerés (paraphrase-multilingual-MiniLM-L12-v2)
- Relevancia-score ranking (4 összetevő, súlyozott összeg)
- TF-IDF + cosine similarity témamodellezés, trend-score számítással
- FTS5 teljes szöveges keresés, szűrőkkel (forrás, dátum, entitás, téma)
- Automatikus hírlevél HTML kimenet
- Háttérszálas pipeline, SQLite job perzisztenciával
- Automatikus Ollama subprocess kezelés, párhuzamos job védelemmel

## Könyvtárstruktúra

```text
news_summarizer/
├── app.py
├── config.py
├── feeds.yaml
├── prompt_builder.py
├── requirements.txt
├── output/
│   ├── news.db
│   ├── news.md
│   ├── summary.html
│   └── newsletter.html
├── services/
│   ├── db_service.py        # Adatbázis-réteg, FTS5 séma
│   ├── search_service.py    # FTS5 keresés, snippet generálás
│   ├── feed_service.py
│   ├── scrape_service.py
│   ├── translate_service.py
│   ├── ner_service.py
│   ├── keyword_service.py
│   ├── relevance_service.py
│   ├── topic_service.py
│   ├── newsletter_service.py
│   ├── markdown_service.py
│   ├── html_service.py
│   ├── ollama_service.py
│   ├── job_service.py
│   └── pipeline_service.py
├── static/
│   └── app.js
└── templates/
    ├── base.html
    ├── index.html
    ├── search.html
    ├── article.html
    ├── browse.html
    ├── admin.html
    └── 404.html
```

## Indítás

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

A felület: `http://127.0.0.1:5000`

## Oldalak

| URL | Leírás |
|---|---|
| `/` | Főoldal: pipeline indítás, NLP panelek, összefoglaló |
| `/search` | Keresőoldal: FTS5 + szűrők (forrás, dátum, entitás, téma) |
| `/article/<id>` | Cikkoldal: teljes szöveg, entitások, kulcsszavak, relevancia, témák |
| `/browse` | Témaböngésző: TF-IDF klaszterek trend szerint |
| `/admin` | Admin: DB statisztikák, forráskezelés, job előzmények |
| `/newsletter` | Legutóbbi hírlevél HTML |

## API végpontok

| Végpont | Leírás |
|---|---|
| `POST /run` | Pipeline indítása `{"window":"24h"}` |
| `GET /status/<job_id>` | Job állapot |
| `GET /api/search?q=…` | JSON keresési eredmények |
| `GET /api/top-entities?window=24h` | Leggyakoribb entitások |
| `GET /api/top-keywords?window=24h` | Leggyakoribb kulcsszavak |
| `GET /api/topics?window=24h` | Aktuális témák |
| `GET /api/topic/<id>` | Egy téma részletei |
| `GET /api/entities/<id>` | Egy cikk entitásai |
| `GET /api/keywords/<id>` | Egy cikk kulcsszavai |

## Pipeline lépései

1. RSS feedek beolvasása
2. URL-cache ellenőrzés
3. Cikk scrape és szövegtisztítás
4. Tartalom-hash duplikátumszűrés
5. Fordítás magyarra
6. Extraktív mini-összefoglaló
7. SQLite mentés (FTS5 triggerek automatikusan indexelik)
8. GLiNER entitáskinyerés
9. KeyBERT kulcsszókinyerés
10. Relevancia-score batch számítás
11. TF-IDF témamodellezés
12. Hírlevél HTML generálása
13. news.md előállítása
14. Ollama inferencia
15. HTML renderelés és mentés

## FTS5 keresés

Az `articles_fts` virtuális tábla a `title`, `mini_summary_hu` és `content_hu`
mezőket indexeli. INSERT/UPDATE/DELETE triggerek tartják szinkronban az `articles`
táblával – manuális újraindexelés nem szükséges.

Meglévő adatbázison az első indításkor az `_migrate` függvény automatikusan
feltölti az FTS indexet, ha az még üres.

A keresés BM25 relevancia szerint rangsorol. Szűrési lehetőségek: forrás,
dátum intervallum, entitás szöveg, téma ID.

## Relevancia-score

| Összetevő | Súly | Leírás |
|---|---|---|
| Forrásszám | 35% | Kulcsszó-átfedés alapú forrásszámlálás |
| Frissesség | 25% | Exponenciális bomlás, 12 h felezési idő |
| Entitássúly | 25% | tanh(count/5) × átlagos GLiNER konfidencia |
| Kulcsszósúly | 15% | Top-5 KeyBERT kulcsszó átlagos értéke |

## Adatbázis séma

| Tábla | Leírás |
|---|---|
| `sources` | RSS források |
| `articles` | Cikkek + `relevance_score` |
| `article_keywords` | KeyBERT kulcsszavak |
| `article_entities` | GLiNER entitások |
| `topics` | TF-IDF klaszterek |
| `article_topics` | Cikk–téma kapcsolatok |
| `articles_fts` | FTS5 virtuális tábla (title, mini_summary_hu, content_hu) |
| `summaries` | Ollama összefoglalók |
| `jobs` | Pipeline job állapotok |

## Konfigurációs paraméterek (config.py)

| Paraméter | Alapértelmezett | Leírás |
|---|---|---|
| `OLLAMA_MODEL` | `llama3.2:3b` | Helyi Ollama modell |
| `MAX_ENTRIES_PER_RUN` | `30` | RSS bejegyzések korlátja futásonként |
| `MAX_SUMMARY_ITEMS` | `14` | Ollama promptba kerülő cikkek száma |
| `MAX_ARTICLE_CHARS` | `12000` | Cikkszöveg karakterkorlátja |
| `OLLAMA_NUM_PREDICT` | `700` | Generált tokenek maximuma |
| `OLLAMA_TEMPERATURE` | `0.2` | Inferencia hőmérséklet |

## Korlátok

- A témamodellezés szóalak-alapú (TF-IDF), nem szemantikus
- A mini-összefoglaló extraktív, nem absztraktív
- Nincs felhasználói authentikáció (5. fázis)
- Nincs ütemezett automatikus futtatás (5. fázis)
