# Hírösszefoglaló és médiamegfigyelő rendszer – fejlesztési koncepció

## 1. Bevezetés

A rendszer egy RSS-alapú hírgyűjtő és összefoglaló eszköz, amely különböző forrásokból
cikkeket gyűjt, feldolgoz, majd magyar nyelvű összefoglalót készít belőlük lokális
Ollama inferenciával.

A fejlesztés célja egy komplexebb, többfunkciós platform kialakítása, amely:

* többnyelvű forrásokat kezel és fordít
* NLP-alapú entitáskinyerést, kulcsszavazást, témamodellezést és relevancia-rankingot végez
* kereshető adatbázist épít
* webes felületen teszi elérhetővé az információt
* automatizált hírlevelet generál

---

## 2. Fejlesztési alapelvek

A rendszer fejlesztése modulárisan, egymásra épülő rétegekben történik:

1. stabil adatgyűjtés és tárolás
2. gazdagított metaadatok és NLP-alapú feldolgozás
3. tematikus szervezés és hírlevél
4. keresés és webes felület bővítés
5. intézményi funkciók

---

## 3. Adatmodell (SQLite, jövőben PostgreSQL)

A rendszer SQLite-on fut. PostgreSQL migráció az 5. fázisban, intézményi igény esetén.

### 3.1. sources ✅
RSS források metaadatai. Pipeline indulásakor szinkronizálódik a `feeds.yaml`-ból.

### 3.2. articles ✅
Feldolgozott cikkek: url, title, source, lang, country, category, published,
scraped_at, content, content_hu, content_hash, mini_summary_hu, relevance_score.

### 3.3. article_keywords ✅
KeyBERT kulcsszavak: article_id, keyword, score.

### 3.4. article_entities ✅
GLiNER entitások: article_id, entity_text, entity_type (PERSON/ORG/LOCATION/EVENT/PRODUCT), score.

### 3.5. topics ✅
TF-IDF klaszterek: window, created_at, label, keywords, article_count, trend_score.

### 3.6. article_topics ✅
Cikk–téma kapcsolatok: article_id, topic_id, similarity.

### 3.7. summaries ✅
Időablakos Ollama összefoglalók: window, created_at, content_md, html, source_count.

### 3.8. jobs ✅
Pipeline job állapotok: job_id, stage, progress, message, html, error, stats, timestamps.

---

## 4. Feldolgozási pipeline ✅

### 4.1. Ingest ✅
RSS feldolgozás · URL-cache · scrape · duplikátumszűrés · fordítás · mini-összefoglaló · mentés

### 4.2. NLP feldolgozás ✅
GLiNER entitáskinyerés · KeyBERT kulcsszókinyerés · relevancia-score batch számítás

### 4.3. Témamodellezés ✅
TF-IDF + cosine similarity klaszterezés · trend-score számítás · cikk–téma hozzárendelés

### 4.4. Kimenet ✅
Hírlevél HTML generálása · news.md előállítása · Ollama inferencia · HTML renderelés

---

## 5. NLP réteg

### 5.1. Kulcsszókinyerés ✅
* Modell: `paraphrase-multilingual-MiniLM-L12-v2` (KeyBERT, ~120 MB)
* Módszer: Max Marginal Relevance – relevancia és diverzitás egyensúlya
* Cikkenként max 10 kulcsszó, 0.2 score küszöb felett
* Frontend: intenzitás-alapú kék hőtérkép panel

### 5.2. Entitáskinyerés ✅
* Modell: `enyaml/gliner-multi-v2.1` (GLiNER, ~400 MB)
* Típusok: PERSON, ORG, LOCATION, EVENT, PRODUCT
* Szöveg: content_hu, 1500 karakteres ablakokban
* Frontend: típusonként csoportosított badge nézet

### 5.3. Relevancia-score ✅

| Összetevő | Súly | Módszer |
|---|---|---|
| Forrásszám | 35% | Kulcsszó-átfedés alapú forrásszámlálás |
| Frissesség | 25% | Exponenciális bomlás, 12 h felezési idő |
| Entitássúly | 25% | tanh(count/5) × átlagos konfidencia |
| Kulcsszósúly | 15% | Top-5 kulcsszó átlagos relevancia-értéke |

### 5.4. Témamodellezés ✅
* Módszer: TF-IDF vektorizálás + cosine similarity, mohó agglomeratív klaszterezés
* Bemenet: mini_summary_hu + kulcsszavak
* Hasonlósági küszöb: 0.25 · Minimális klaszterméret: 2 cikk
* Téma-felirat: összesített TF-IDF top 4 term
* Trend-score: `átlagos relevancia × log(klaszterméret + 1)`
* Frontend: témapanel cikkcímekkel és trend-score-ral
* Korlát: nem szemantikus – hasonló értelmű, eltérő szavú cikkek különválhatnak

---

## 6. Hírlevél ✅

Automatikus HTML kimenet (`output/newsletter.html`):
* Témák szerint szervezett szerkezet
* Cikkenként: cím (link), forrás, dátum, mini-összefoglaló, kulcsszó-badge-ek, relevancia %
* Trend-score és cikkszám téma-fejlécben
* Inline CSS az e-mail kliens kompatibilitásért
* Elérhető a `/newsletter` végponton

---

## 7. Keresőmotor és webes felület

### 7.1. Webes felület aktuális állapota ✅
* Pipeline indítás, időablak-választó, hírlevél link
* Progress bar 15 lépéses pipeline-hoz
* Statisztikai panel (13 mutató)
* Entitáspanel · Kulcsszópanel · Témapanel
* Összefoglaló iframe

### 7.2. Tervezett bővítések *(4. fázis)*
* Teljes szöveges keresés (SQLite FTS5)
* Cikkoldal (szöveg, entitások, kulcsszavak, téma, relevancia)
* Témaböngésző időbeli trenddel
* Admin felület

---

## 8. Fejlesztési fázisok

### Fázis 1 – Adatmodell és infrastruktúra ✅
sources + jobs DB perzisztencia · bugfixek · PostgreSQL migráció halasztva

### Fázis 2 – NLP réteg ✅
GLiNER entitáskinyerés · KeyBERT kulcsszókinyerés · relevancia-score · frontend panelek

### Fázis 3 – Témamodellezés és hírlevél ✅
TF-IDF + cosine similarity klaszterezés · trend-score · cikk–téma kapcsolatok ·
automatikus hírlevél HTML · témapanel a frontenden

### Fázis 4 – Keresőmotor és webes UI bővítés
* Teljes szöveges keresés (SQLite FTS5)
* Cikkoldal, témaböngésző, admin felület

### Fázis 5 – Intézményi funkciók
* Felhasználói fiókok, mentett keresések, értesítések
* PostgreSQL migráció (ha szükséges)
* Automatizált riportok és ütemezett futtatás

---

## 9. Könyvtári alkalmazhatóság

A rendszer jól illeszkedik szakkönyvtári felhasználásra:

* többnyelvű forrásokat kezel és fordít
* entitáskinyeréssel és kulcsszavazással támogatja a tematikus feltárást
* témamodellezés segíti a cikkcsoportok azonosítását
* relevancia-ranking kiemeli a fontos híreket
* automatikus hírlevél-generálás támogatja a médiakövetési riportokat
* kereshető tudásbázist épít (4. fázistól)

---

## 10. Összegzés

Az 1–3. fejlesztési fázis teljes egészében elkészült. A rendszer jelenleg:

* stabil adatgyűjtési és tárolási réteggel rendelkezik (1. fázis)
* GLiNER entitáskinyerést, KeyBERT kulcsszavazást és relevancia-rankingot végez (2. fázis)
* TF-IDF alapú témamodellezést futtat és automatikus hírleveleket generál (3. fázis)
* a frontenden három NLP-panel (entitás, kulcsszó, téma) mutatja az eredményeket

A következő fejlesztési irány a 4. fázis: teljes szöveges keresés és kibővített
webes felület, amelyhez az NLP metaadatok (entitások, kulcsszavak, témák) már
teljes egészében rendelkezésre állnak.
