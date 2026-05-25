# Hírösszefoglaló és médiamegfigyelő rendszer – fejlesztési koncepció

## 1. Bevezetés

A rendszer egy RSS-alapú hírgyűjtő és összefoglaló eszköz, amely különböző forrásokból
cikkeket gyűjt, feldolgoz, majd magyar nyelvű összefoglalót készít belőlük lokális
Ollama inferenciával.

A fejlesztés célja egy komplexebb, többfunkciós platform kialakítása, amely:

* többnyelvű forrásokat kezel és fordít
* teljes szövegeket tárol
* NLP-alapú entitáskinyerést, kulcsszavazást és relevancia-rankingot végez
* témamodellezést alkalmaz
* kereshető adatbázist épít
* webes felületen teszi elérhetővé az információt

---

## 2. Fejlesztési alapelvek

A rendszer fejlesztése modulárisan, egymásra épülő rétegekben történik:

1. stabil adatgyűjtés és tárolás
2. gazdagított metaadatok és NLP-alapú feldolgozás
3. tematikus szervezés
4. keresés és webes felület bővítés
5. automatizált összefoglalás és intézményi funkciók

---

## 3. Adatmodell (SQLite, jövőben PostgreSQL)

A rendszer SQLite-on fut. PostgreSQL migráció akkor indokolt, ha intézményi vagy
többfelhasználós telepítés válik szükségessé, vagy teljes szöveges keresés (FTS) igénye merül fel.

### 3.1. sources ✅

RSS források metaadatai (name, lang, country, category, rss_url).
Pipeline indulásakor szinkronizálódik a `feeds.yaml`-ból.

### 3.2. articles ✅

A rendszer központi eleme:

* cikk alapadatok (url, title, source, lang, country, category, published)
* scraped_at, content (eredeti), content_hu (fordított)
* content_hash (duplikátumszűrés), mini_summary_hu
* **relevance_score** – számított relevancia-pontszám (2. fázis)

### 3.3. article_keywords ✅

KeyBERT kulcsszavak: article_id, keyword, score (KeyBERT relevancia-érték).

### 3.4. article_entities ✅

GLiNER entitások: article_id, entity_text, entity_type, score (konfidencia).
Típusok: PERSON, ORG, LOCATION, EVENT, PRODUCT.

### 3.5. topics és article_topics

Témamodellezésből származó klaszterek és kapcsolatok. *(3. fázis)*

### 3.6. summaries ✅

Időablakos Ollama összefoglalók (window, created_at, content_md, html, source_count).

### 3.7. jobs ✅

Pipeline job állapotok SQLite-ban (job_id, stage, progress, message, html, error, stats, timestamps).

---

## 4. Feldolgozási pipeline

### 4.1. Ingest (cikkbegyűjtés) ✅

* RSS feldolgozás (feedparser, kétféle dátumformátum kezelésével)
* URL-cache ellenőrzés
* Cikk letöltés (trafilatura + requests fallback)
* Főszöveg kinyerés és szövegtisztítás
* Tartalom-hash duplikációszűrés (első 8 mondat SHA-256)
* Teljes szöveg mentése (eredeti + magyar fordítás)
* Extraktív mini-összefoglaló generálása

### 4.2. NLP feldolgozás ✅

* GLiNER entitáskinyerés (enyaml/gliner-multi-v2.1, ~400 MB) ✅
* KeyBERT kulcsszókinyerés (paraphrase-multilingual-MiniLM-L12-v2, ~120 MB) ✅
* Relevancia-score számítás (batch, forrásszám + frissesség + entitás + kulcsszó) ✅

### 4.3. Összefoglalás ✅

* news.md előállítása relevancia szerint rendezett cikkekből
* Ollama inferencia (llama3.2:3b, helyi)
* HTML renderelés (markdown-it)

### 4.4. Batch feldolgozás (cron)

* Napi feldolgozás és újrasúlyozás
* Heti témamodellezés és trendszámítás
* Automatikus összefoglalók

*(3. fázis)*

---

## 5. NLP réteg

### 5.1. Kulcsszókinyerés ✅

* Modell: `paraphrase-multilingual-MiniLM-L12-v2` (KeyBERT, ~120 MB)
* Módszer: Max Marginal Relevance (MMR) – relevancia és diverzitás egyensúlya
* Szókapcsolat hossza: unigram + bigram
* Cikkenként maximum 10 kulcsszó, 0.2 score küszöb felett
* Frontend: időablakos kulcsszópanel, intenzitás-alapú kék hőtérkép nézetben

### 5.2. Entitáskinyerés ✅

* Modell: `enyaml/gliner-multi-v2.1` (GLiNER, ~400 MB)
* Felismert típusok: PERSON, ORG, LOCATION, EVENT, PRODUCT
* Szöveg: content_hu (teljes fordított szöveg), 1500 karakteres ablakokban
* Deduplikáció: azonos (text, type) párból csak a legjobb score marad
* Konfidencia küszöb: 0.4
* Frontend: típusonként csoportosított badge nézet, előfordulásszámmal

### 5.3. Relevancia-score ✅

Négy összetevő súlyozott összege (0.0–1.0):

| Összetevő | Súly | Módszer |
|---|---|---|
| Forrásszám | 35% | Kulcsszó-átfedés alapján azonosított egyező témájú cikkek forrásainak száma |
| Frissesség | 25% | Exponenciális bomlás, 12 órás felezési idővel |
| Entitássúly | 25% | tanh(count/5) × átlagos GLiNER konfidencia |
| Kulcsszósúly | 15% | Top-5 KeyBERT kulcsszó átlagos relevancia-értéke |

A score batch-ben számítódik az időablakon belüli összes cikken,
így a source_score a cache-elt korábbi cikkeket is figyelembe veszi.

### 5.4. Témamodellezés *(3. fázis)*

* Klaszterek képzése
* Időbeli trendek azonosítása
* Javasolt eszköz: BERTopic vagy TF-IDF + cosine similarity

---

## 6. Keresőmotor és webes felület

### 6.1. Webes felület aktuális állapota ✅

* Pipeline indítás, időablak-választó
* Progress bar valós idejű job státusszal (13 lépés)
* Statisztikai panel (RSS, cache, scrape, NER, kulcsszó, fordítás)
* Entitáspanel: leggyakoribb entitások típusonként, badge nézetben
* Kulcsszópanel: leggyakoribb kulcsszavak, relevancia-intenzitású hőtérkép
* Összefoglaló: iframe-ben megjelenő HTML kimenet

### 6.2. Tervezett webes bővítések *(4. fázis)*

* Teljes szöveges keresés (SQLite FTS5 vagy PostgreSQL tsvector)
* Cikkoldal (eredeti + fordított szöveg, entitások, kulcsszavak, relevancia-score)
* Témaböngésző
* Admin felület

---

## 7. Relevancia és rangsorolás ✅

Megvalósítva a 2. fázisban. A relevancia-score az Ollama prompt összeállításában
is érvényesül: a `list_articles_since` relevancia szerint csökkenő sorrendben adja
vissza a cikkeket, és a top `MAX_SUMMARY_ITEMS` cikk kerül a promptba.

---

## 8. Fejlesztési fázisok

### Fázis 1 – Adatmodell és infrastruktúra ✅

* sources tábla (feeds.yaml normalizálása) ✅
* jobs tábla (JSON fájlok kiváltása DB perzisztenciával) ✅
* Bugfixek: chunk_text rfind, published UTC normalizálás, párhuzamos job guard ✅
* PostgreSQL migráció halasztva – intézményi igény esetén kerül vissza (5. fázis)

### Fázis 2 – NLP réteg ✅

* GLiNER entitáskinyerés ✅
* KeyBERT kulcsszókinyerés ✅
* Relevancia-score (forrásszám + frissesség + entitássúly + kulcsszósúly) ✅
* Frontend: entitáspanel + kulcsszópanel ✅
* Relevancia-alapú cikk-rendezés az Ollama promptban ✅

### Fázis 3 – Témamodellezés és trendanalízis

* Klaszterezés (BERTopic vagy TF-IDF + cosine similarity)
* Időbeli trendek számítása és megjelenítése
* Automatikus hírlevél-generálás

### Fázis 4 – Keresőmotor és webes UI bővítés

* Teljes szöveges keresés (SQLite FTS5)
* Cikkoldal, témaböngésző, admin felület

### Fázis 5 – Intézményi funkciók

* Felhasználói fiókok, mentett keresések
* Automatizált riportok és értesítések
* PostgreSQL migráció (ha szükséges)

---

## 9. Könyvtári alkalmazhatóság

A rendszer jól illeszkedik szakkönyvtári felhasználásra:

* többnyelvű forrásokat kezel és fordít
* entitáskinyeréssel és kulcsszavazással támogatja a tematikus feltárást
* relevancia-ranking segíti a fontos hírek kiemelését
* kereshető tudásbázist épít (4. fázistól)
* automatizálja a médiakövetést

---

## 10. Összegzés

Az 1. és 2. fejlesztési fázis teljes egészében elkészült. A rendszer jelenleg:

* stabil adatgyűjtési és tárolási réteggel rendelkezik
* GLiNER entitáskinyerést és KeyBERT kulcsszavazást végez minden cikken
* relevancia-score alapján rendezi és szűri az összefoglalóba kerülő cikkeket
* a frontenden entitás- és kulcsszópanelen jeleníti meg az NLP eredményeket

A következő fejlesztési irány a 3. fázis: témamodellezés és trendanalízis,
amelyhez az entitás- és kulcsszóadatok már rendelkezésre állnak.
