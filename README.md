# Hírösszefoglaló

RSS-alapú hírgyűjtő, fordító és összefoglaló rendszer, lokális Ollama inferenciával,
GLiNER entitáskinyeréssel, KeyBERT kulcsszavazással, TF-IDF témamodellezéssel,
relevancia-rankinggal és hírlevél-generálással.

## Funkciók

- SQLite alapú helyi tárolás (sources, articles, article_keywords, article_entities,
  topics, article_topics, summaries, jobs)
- URL-szintű cache és tartalom-hash duplikátumszűrés
- Többnyelvű RSS feldolgozás: hu, en, de, fr
- Chunkolt fordítás magyarra (`deep-translator`)
- Extraktív mini-összefoglaló (első N mondat)
- GLiNER entitáskinyerés (PERSON, ORG, LOCATION, EVENT, PRODUCT)
- KeyBERT kulcsszókinyerés (paraphrase-multilingual-MiniLM-L12-v2)
- Relevancia-score ranking (forrásszám + frissesség + entitássúly + kulcsszósúly)
- TF-IDF + cosine similarity témamodellezés, trend-score számítással
- Automatikus hírlevél HTML kimenet (témák szerint szervezett)
- Háttérszálas pipeline, job állapot SQLite-ban perzisztálva
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
│   └── newsletter.html       # Hírlevél kimenet
├── services/
│   ├── db_service.py
│   ├── feed_service.py
│   ├── scrape_service.py
│   ├── translate_service.py
│   ├── ner_service.py
│   ├── keyword_service.py
│   ├── relevance_service.py
│   ├── topic_service.py      # TF-IDF témamodellezés
│   ├── newsletter_service.py # Hírlevél HTML generálás
│   ├── markdown_service.py
│   ├── html_service.py
│   ├── ollama_service.py
│   ├── job_service.py
│   └── pipeline_service.py
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

Ollama modell (ha még nincs):

```bash
ollama pull llama3.2:3b
```

A GLiNER (~400 MB) és a KeyBERT modell (~120 MB) az első pipeline futáskor
töltődnek le automatikusan a Hugging Face hub-ról. A témamodellezés offline,
külön modell nem szükséges.

## API végpontok

| Végpont | Metódus | Leírás |
|---|---|---|
| `/` | GET | Főoldal |
| `/run` | POST | Pipeline indítása `{"window": "24h"}` payloaddal |
| `/status/<job_id>` | GET | Job állapot |
| `/entities/<article_id>` | GET | Egy cikk entitásai |
| `/keywords/<article_id>` | GET | Egy cikk kulcsszavai |
| `/top-entities?window=24h` | GET | Leggyakoribb entitások |
| `/top-keywords?window=24h` | GET | Leggyakoribb kulcsszavak |
| `/topics?window=24h` | GET | Aktuális témák trend szerint |
| `/newsletter` | GET | Legutóbbi hírlevél HTML |

Időablak értékek: `12h`, `24h`, `7d`.

## Pipeline lépései

1. RSS feedek beolvasása és időablak szerinti szűrés
2. URL-cache ellenőrzés
3. Cikk scrape és szövegtisztítás
4. Tartalom-hash duplikátumszűrés
5. Fordítás magyarra
6. Extraktív mini-összefoglaló
7. SQLite mentés
8. GLiNER entitáskinyerés
9. KeyBERT kulcsszókinyerés
10. Relevancia-score batch számítás
11. TF-IDF témamodellezés + cikk–téma hozzárendelés
12. Hírlevél HTML generálása
13. `news.md` előállítása
14. Ollama inferencia
15. HTML renderelés és mentés

## Témamodellezés

Módszer: TF-IDF vektorizálás + cosine similarity alapú mohó agglomeratív klaszterezés.

- Bemenet: `mini_summary_hu` + cikk kulcsszavak összefűzve
- Hasonlósági küszöb: 0.25 (hangolható a `topic_service.py`-ban)
- Minimális klaszterméret: 2 cikk
- Téma-felirat: a klaszter összesített TF-IDF súlyainak top 4 terme
- Trend-score: `átlagos relevancia × log(klaszterméret + 1)`
- Előny: teljesen offline, gyors, nincs külön modell
- Korlát: nem szemantikus – hasonló értelmű, eltérő szavú cikkek különválhatnak

## Hírlevél

Az `output/newsletter.html` témák szerint szervezett, önálló HTML oldal:
- Fejléc: dátum, időablak, statisztikák
- Témacsoportok: top 4 cikk relevancia szerint, kulcsszó-badgekkel
- Lábléc: forrás lista
- Inline CSS (e-mail kliensben is megjeleníthető)

A hírlevél a `/newsletter` végponton is elérhető közvetlenül a böngészőből.

## Relevancia-score

| Összetevő | Súly | Leírás |
|---|---|---|
| Forrásszám | 35% | Hány forrás ír hasonló témáról |
| Frissesség | 25% | Exponenciális bomlás, 12 h felezési idővel |
| Entitássúly | 25% | tanh(count/5) × átlagos GLiNER konfidencia |
| Kulcsszósúly | 15% | Top-5 KeyBERT kulcsszó átlaga |

## Adatbázis séma

| Tábla | Leírás |
|---|---|
| `sources` | RSS források |
| `articles` | Cikkek + `relevance_score` |
| `article_keywords` | KeyBERT kulcsszavak |
| `article_entities` | GLiNER entitások |
| `topics` | TF-IDF klaszterek (label, keywords, article_count, trend_score) |
| `article_topics` | Cikk–téma kapcsolatok (similarity) |
| `summaries` | Ollama összefoglalók |
| `jobs` | Pipeline job állapotok |

## Korlátok

- A témamodellezés nem szemantikus (TF-IDF szóalak alapú)
- A mini-összefoglaló extraktív, nem absztraktív
- Nincs teljes szöveges keresés (4. fázis)
- Nincs felhasználói authentikáció (5. fázis)
