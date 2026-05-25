# Hírösszefoglaló és médiamegfigyelő rendszer – fejlesztési koncepció

## 1. Bevezetés

A rendszer egy RSS-alapú hírgyűjtő és összefoglaló eszköz, amely különböző forrásokból
cikkeket gyűjt, feldolgoz, majd magyar nyelvű összefoglalót készít belőlük lokális
Ollama inferenciával. A rendszer NLP-alapú entitáskinyerést, kulcsszavazást,
témamodellezést, relevancia-rankingot, teljes szöveges keresést és hírlevél-generálást
végez, teljes egészében lokálisan, internet-hozzáférés nélkül is működőképesen
(az első modelltöltés után).

---

## 2. Fejlesztési alapelvek

Moduláris, egymásra épülő rétegek:

1. Stabil adatgyűjtés és tárolás
2. NLP-alapú metaadat-gazdagítás
3. Tematikus szervezés és hírlevél
4. Keresés és webes felület
5. Intézményi funkciók

---

## 3. Adatmodell (SQLite)

### 3.1. sources ✅
RSS források (name, lang, country, category, rss_url). Pipeline indulásakor szinkronizálódik.

### 3.2. articles ✅
Feldolgozott cikkek: url, title, source, lang, country, category, published,
scraped_at, content, content_hu, content_hash, mini_summary_hu, relevance_score.

### 3.3. article_keywords ✅
KeyBERT kulcsszavak: article_id, keyword, score.

### 3.4. article_entities ✅
GLiNER entitások: article_id, entity_text, entity_type, score.

### 3.5. topics ✅
TF-IDF klaszterek: window, created_at, label, keywords, article_count, trend_score.

### 3.6. article_topics ✅
Cikk–téma kapcsolatok: article_id, topic_id, similarity.

### 3.7. articles_fts ✅
FTS5 virtuális tábla: title, mini_summary_hu, content_hu indexelve.
INSERT/UPDATE/DELETE triggerekkel szinkronizálva az articles táblával.

### 3.8. summaries ✅
Időablakos Ollama összefoglalók.

### 3.9. jobs ✅
Pipeline job állapotok.

PostgreSQL migráció az 5. fázisban, intézményi igény esetén.

---

## 4. Feldolgozási pipeline ✅

1. RSS beolvasás · 2. URL-cache · 3. Scrape · 4. Duplikátumszűrés ·
5. Fordítás · 6. Mini-összefoglaló · 7. Mentés (FTS5 trigger) ·
8. GLiNER NER · 9. KeyBERT kulcsszavak · 10. Relevancia-score ·
11. TF-IDF témamodellezés · 12. Hírlevél · 13. news.md · 14. Ollama · 15. HTML

---

## 5. NLP réteg ✅

### 5.1. Kulcsszókinyerés ✅
KeyBERT + paraphrase-multilingual-MiniLM-L12-v2 (~120 MB) · MMR · max 10 kulcsszó/cikk

### 5.2. Entitáskinyerés ✅
GLiNER + enyaml/gliner-multi-v2.1 (~400 MB) · PERSON, ORG, LOCATION, EVENT, PRODUCT

### 5.3. Relevancia-score ✅
Forrásszám (35%) + Frissesség (25%) + Entitássúly (25%) + Kulcsszósúly (15%)

### 5.4. Témamodellezés ✅
TF-IDF + cosine similarity · mohó agglomeratív klaszterezés ·
trend-score = átlagos relevancia × log(klaszterméret + 1) ·
korlát: szóalak-alapú, nem szemantikus

---

## 6. Keresőmotor ✅

### 6.1. FTS5 teljes szöveges keresés ✅
* Virtuális tábla: `articles_fts` (title, mini_summary_hu, content_hu)
* Tokenizáció: unicode61 (diakritikus karaktereket kezel)
* Rangsorolás: BM25 (beépített FTS5 függvény)
* Szűrők: forrás, dátum intervallum, entitás, téma ID
* Snippet generálás: keresési kifejezés kiemelése `<mark>` tagekkel
* Lapozás: oldalméretes eredmény, oldalszám navigációval
* Meglévő DB automatikus FTS újraindexelése első indításkor

### 6.2. Keresési API ✅
`GET /api/search?q=…&source=…&from=…&to=…&entity=…&topic_id=…&page=…`

---

## 7. Webes felület ✅

### 7.1. Főoldal (`/`) ✅
Pipeline indítás · időablak választó · progress bar · statisztikai panel ·
entitás-, kulcsszó-, témapanel · összefoglaló iframe · hírlevél link

### 7.2. Keresőoldal (`/search`) ✅
FTS5 keresés · szűrősor (forrás, dátum, entitás, téma) ·
snippet kiemelés · lapozás · találatszám

### 7.3. Cikkoldal (`/article/<id>`) ✅
Teljes magyar szöveg (összecsukható) · entitások (kattintható keresőlink) ·
kulcsszavak (kattintható keresőlink) · relevancia-score + összetevők ·
téma-badge-ek (böngészőre mutató link)

### 7.4. Témaböngésző (`/browse`) ✅
TF-IDF klaszterek trend szerint · trend-bar vizualizáció ·
ablak-választó (12h/24h/7d) · cikklinkek · keresőre mutató link

### 7.5. Admin panel (`/admin`) ✅
DB statisztikák · RSS források listája · job előzmények (20 legutóbbi)

### 7.6. Navigáció ✅
Közös `base.html` alapsablon · sticky navigációs sáv minden oldalon ·
404 hibaoldal

---

## 8. Fejlesztési fázisok

### Fázis 1 – Adatmodell és infrastruktúra ✅
sources + jobs DB · bugfixek · PostgreSQL migráció halasztva

### Fázis 2 – NLP réteg ✅
GLiNER · KeyBERT · relevancia-score · frontend panelek

### Fázis 3 – Témamodellezés és hírlevél ✅
TF-IDF klaszterezés · trend-score · hírlevél HTML · témapanel

### Fázis 4 – Keresőmotor és webes UI ✅
FTS5 teljes szöveges keresés · keresőoldal · cikkoldal ·
témaböngésző · admin panel · közös navigáció

### Fázis 5 – Intézményi funkciók
* Felhasználói fiókok, mentett keresések, e-mail értesítések
* Ütemezett automatikus futtatás (cron / APScheduler)
* PostgreSQL migráció (FTS5 → tsvector, ha szükséges)
* Automatizált riportok exportálása (PDF, DOCX)

---

## 9. Könyvtári alkalmazhatóság

* Többnyelvű forráskezelés és fordítás
* Entitáskinyerés és kulcsszavazás a tematikus feltáráshoz
* Témamodellezés a cikkcsoportok azonosításához
* Teljes szöveges keresés a tudásbázisban
* Relevancia-ranking a fontos hírek kiemelésére
* Automatikus hírlevél médiakövetési riportokhoz
* Cikkoldal részletes metaadatokkal

---

## 10. Összegzés

Az 1–4. fejlesztési fázis teljes egészében elkészült. A rendszer jelenleg:

* Stabil adatgyűjtési, fordítási és tárolási réteggel rendelkezik
* GLiNER NER-t, KeyBERT kulcsszavazást és relevancia-rankingot végez
* TF-IDF témamodellezést és automatikus hírlevél-generálást futtat
* FTS5 teljes szöveges keresést biztosít szűrőkkel és snippet kiemelésekkel
* Négy felhasználói oldalt kínál: főoldal, keresés, cikkoldal, témaböngésző
* Admin panelen látható a DB állapota, a forráskezelés és a job előzmények

A következő és egyben utolsó fejlesztési irány az 5. fázis:
felhasználói fiókok, ütemezett futtatás, PostgreSQL opció és exportálás.
