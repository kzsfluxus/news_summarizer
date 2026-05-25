# Hírösszefoglaló és médiamegfigyelő rendszer – fejlesztési koncepció

## 1. Bevezetés

A rendszer egy RSS-alapú hírgyűjtő és összefoglaló eszköz, amely különböző forrásokból cikkeket gyűjt, feldolgoz, majd magyar nyelvű összefoglalót készít belőlük lokális Ollama inferenciával.

A fejlesztés célja egy komplexebb, többfunkciós platform kialakítása, amely:

* többnyelvű forrásokat kezel és fordít
* teljes szövegeket tárol
* NLP-alapú entitáskinyerést és tárgyszavazást végez
* témamodellezést alkalmaz
* kereshető adatbázist épít
* webes felületen teszi elérhetővé az információt

Ez a rendszer túlmutat egy egyszerű híraggregátoron, és egy digitális médiamegfigyelő, illetve információfeltáró eszköz irányába fejlődik.

---

## 2. Fejlesztési alapelvek

A rendszer fejlesztése modulárisan, egymásra épülő rétegekben történik:

1. stabil adatgyűjtés és tárolás
2. gazdagított metaadatok
3. NLP-alapú feldolgozás
4. tematikus szervezés
5. keresés és webes felület
6. automatizált összefoglalás és hírlevélkészítés

Ez biztosítja, hogy minden fejlesztési szint önállóan is használható maradjon.

---

## 3. Adatmodell (SQLite, jövőben PostgreSQL)

A rendszer jelenleg SQLite-on fut. PostgreSQL migráció akkor indokolt, ha intézményi/többfelhasználós telepítés válik szükségessé, vagy a teljes szöveges keresés (FTS) igénye felmerül.

### 3.1. sources ✅

A hírcsatornák és források metaadatai (name, lang, country, category, rss_url). Pipeline indulásakor szinkronizálódik a `feeds.yaml`-ból.

### 3.2. articles ✅

A rendszer központi eleme:

* cikk alapadatok (url, title, source, lang, country, category, published)
* scrape metaadatok (scraped_at)
* tisztított teljes szöveg eredeti nyelven (content)
* magyar fordítás (content_hu)
* kivonatok (mini_summary_hu, context_hu)
* tartalom-ujjlenyomat (content_hash) – duplikátumszűréshez

### 3.3. article_keywords

Automatikusan generált, súlyozott tárgyszavak. *(2. fázis fennmaradó feladata)*

### 3.4. article_entities ✅

Felismert entitások GLiNER alapján: PERSON, ORG, LOCATION, EVENT, PRODUCT. Minden entitáshoz tárolt mezők: entity_text, entity_type, score (konfidencia).

### 3.5. topics és article_topics

Témamodellezésből származó klaszterek és kapcsolatok. *(3. fázis)*

### 3.6. summaries ✅

Időablakos (12h / 24h / 7d) Ollama összefoglalók: window, created_at, content_md, html, source_count.

### 3.7. jobs ✅

Pipeline job állapotok SQLite-ban: job_id, stage, progress, message, html, error, stats (JSON), created_at, updated_at.

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

### 4.2. NLP feldolgozás ✅ (részben)

* Entitáskinyerés – GLiNER `enyaml/gliner-multi-v2.1` modellel, a teljes magyar szövegen ✅
* Kulcsszókinyerés és súlyozott tárgyszavazás *(2. fázis fennmaradó feladata)*
* Alap relevancia-score *(2. fázis fennmaradó feladata)*

### 4.3. Összefoglalás ✅

* news.md előállítása a mini-összefoglalókból
* Ollama inferencia (`llama3.2:3b`, helyi)
* HTML renderelés (markdown-it)

### 4.4. Batch feldolgozás (cron)

* Napi feldolgozás és újrasúlyozás
* Heti témamodellezés
* Trendek számítása
* Automatikus összefoglalók

*(3. fázis)*

---

## 5. NLP réteg

### 5.1. Tárgyszavazás *(2. fázis fennmaradó feladata)*

* Kulcsszavak súlyozása cím, gyakoriság és kontextus alapján
* Többnyelvű kulcsszavak kezelése
* Cikkenként releváns tárgyszólista
* Javasolt eszköz: YAKE vagy KeyBERT

### 5.2. Entitáskinyerés ✅

* Modell: `enyaml/gliner-multi-v2.1` (GLiNER, ~400 MB, Hugging Face)
* Felismert típusok: PERSON, ORG, LOCATION, EVENT, PRODUCT
* Szöveg: content_hu (teljes fordított szöveg)
* Deduplikáció: azonos (text, type) párból csak a legjobb score marad
* Konfidencia küszöb: 0.4
* Frontend: időablakos entitáspanel, típusonként csoportosítva, előfordulásszámmal

### 5.3. Témamodellezés *(3. fázis)*

* Klaszterek képzése
* Témák súlyozása
* Időbeli trendek azonosítása
* Javasolt eszköz: BERTopic vagy TF-IDF + cosine similarity

---

## 6. Keresőmotor és webes felület

### 6.1. Keresési lehetőségek *(4. fázis)*

* Teljes szöveges keresés (SQLite FTS5 vagy PostgreSQL tsvector)
* Kulcsszó és entitás alapú szűrés
* Dátum és forrás szerinti szűrés
* Témák szerinti keresés

### 6.2. Webes felület aktuális állapota ✅

* Főoldal: pipeline indítás, időablak-választó
* Progress bar valós idejű job státusszal
* Statisztikai panel (RSS, cache, scrape, NER, fordítás)
* Entitáspanel: leggyakoribb entitások típusonként, badge nézetben
* Összefoglaló: iframe-ben megjelenő HTML kimenet

### 6.3. Tervezett webes bővítések *(4. fázis)*

* Keresőfelület
* Cikkoldal (eredeti + fordított szöveg, entitáscímkék)
* Témaböngésző
* Admin felület

---

## 7. Relevancia és rangsorolás *(2. fázis fennmaradó feladata)*

A cikkek súlyozásának tervezett szempontjai:

* több forrásban való megjelenés
* kulcsszavak és entitások súlya
* frissesség
* témasúly
* tartalmi gazdagság

Ez javítja majd az összefoglalók minőségét, a keresési találatok relevanciáját és a hírlevelek tartalmát.

---

## 8. Fejlesztési fázisok

### Fázis 1 – Adatmodell és infrastruktúra ✅

* ~~PostgreSQL bevezetése~~ → SQLite-on maradtunk (PostgreSQL migráció halasztva, intézményi igény esetén visszatér)
* sources tábla (feeds.yaml normalizálása) ✅
* jobs tábla (JSON fájlok kiváltása DB perzisztenciával) ✅
* Bugfixek: chunk_text rfind, published UTC normalizálás, párhuzamos job guard ✅

### Fázis 2 – NLP réteg (részben kész)

* Entitáskinyerés – GLiNER ✅
* Tárgyszavazás (YAKE / KeyBERT) – *következő lépés*
* Alap relevancia-score – *következő lépés*

### Fázis 3 – Témamodellezés és trendanalízis

* Klaszterezés (BERTopic vagy TF-IDF + cosine similarity)
* Időbeli trendek
* Automatikus hírlevél

### Fázis 4 – Keresőmotor és webes UI bővítés

* Teljes szöveges keresés
* Cikkoldal, témaböngésző, admin felület

### Fázis 5 – Intézményi funkciók

* Felhasználói fiókok, mentett keresések
* Automatizált riportok
* PostgreSQL migráció (ha szükséges)

---

## 9. Könyvtári alkalmazhatóság

A rendszer jól illeszkedik szakkönyvtári felhasználásra:

* többnyelvű forrásokat kezel és fordít
* entitáskinyeréssel támogatja a tematikus feltárást
* kereshető tudásbázist épít (4. fázistól)
* automatizálja a médiakövetést
* segíti a gyors szakmai tájékozódást

---

## 10. Összegzés

A rendszer az eredeti prototípusból kinőve egy strukturált, moduláris alkalmazássá vált. Az infrastrukturális alap (DB séma, job perzisztencia, bugfixek) és az NLP réteg első eleme (entitáskinyerés) elkészült.

A következő fejlesztési lépések:

* tárgyszavazás (YAKE / KeyBERT) – a 2. fázis lezárásához
* alap relevancia-score (előfordulásszám + frissesség)
* témamodellezés (3. fázis)
* keresőmotor és kibővített webes UI (4. fázis)

A rendszer már most is önállóan használható médiakövetési eszközként; a tervezett fejlesztések fokozatosan emelik az információfeltárás minőségét és mélységét.
