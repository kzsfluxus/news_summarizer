# Hírösszefoglaló és médiamegfigyelő rendszer – fejlesztési koncepció

## 1. Bevezetés

A jelenlegi rendszer egy RSS-alapú hírgyűjtő és összefoglaló eszköz, amely képes különböző forrásokból cikkeket begyűjteni, feldolgozni, majd ezekből magyar nyelvű összefoglalót készíteni.

A fejlesztés célja ennek a prototípusnak a továbbépítése egy komplexebb, többfunkciós platformmá, amely:

* többnyelvű forrásokat kezel
* teljes szövegeket tárol és fordít
* automatikus tárgyszavazást végez
* témamodellezést alkalmaz
* kereshető adatbázist épít
* webes felületen teszi elérhetővé az információt

Ez a rendszer már túlmutat egy egyszerű híraggregátoron, és egy digitális médiamegfigyelő, illetve információfeltáró eszköz irányába mozdul el.

---

## 2. Fejlesztési alapelvek

A rendszer fejlesztése modulárisan, egymásra épülő rétegekben történjen:

1. stabil adatgyűjtés és tárolás
2. gazdagított metaadatok
3. NLP-alapú feldolgozás
4. tematikus szervezés
5. keresés és webes felület
6. automatizált összefoglalás és hírlevélkészítés

Ez biztosítja, hogy minden fejlesztési szint önállóan is használható maradjon.

---

## 3. Adatmodell (PostgreSQL alapú)

### 3.1. sources

A hírcsatornák és források metaadatai.

### 3.2. articles

A rendszer központi eleme, amely tartalmazza:

* cikk alapadatok (cím, forrás, dátum)
* tisztított teljes szöveg eredeti nyelven
* magyar fordítás
* kivonatok (mini_summary, context)
* hash és feldolgozási státusz

### 3.3. article_keywords

Automatikusan generált, súlyozott tárgyszavak.

### 3.4. article_entities

Felismert entitások (személyek, szervezetek, helyek stb.).

### 3.5. topics és article_topics

Témamodellezésből származó klaszterek és kapcsolatok.

### 3.6. summaries

Időablakos (napi/heti) összefoglalók.

### 3.7. jobs

Feldolgozási és cron feladatok naplózása.

---

## 4. Feldolgozási pipeline

### 4.1. Ingest (cikkbegyűjtés)

* RSS feldolgozás
* cikk letöltés
* főszöveg kinyerés
* tisztítás
* duplikációszűrés
* teljes szöveg mentése
* magyar fordítás
* kivonatok generálása

### 4.2. Azonnali feldolgozás

* kulcsszókinyerés
* súlyozott tárgyszavazás
* entitásfelismerés
* alap relevancia-score

### 4.3. Batch feldolgozás (cron)

* napi feldolgozás és újrasúlyozás
* heti témamodellezés
* trendek számítása
* automatikus összefoglalók

---

## 5. NLP réteg

### 5.1. Tárgyszavazás

* kulcsszavak súlyozása cím, gyakoriság és kontextus alapján
* többnyelvű kulcsszavak kezelése
* cikkenként releváns tárgyszólista

### 5.2. Entitáskinyerés

* személyek
* szervezetek
* helyek
* események

### 5.3. Témamodellezés

* klaszterek képzése
* témák súlyozása
* időbeli trendek azonosítása

---

## 6. Keresőmotor és webes felület

### 6.1. Keresési lehetőségek

* teljes szöveges keresés
* kulcsszó és tárgyszó alapú szűrés
* dátum és forrás szerinti szűrés
* témák szerinti keresés

### 6.2. Webes felület fő elemei

* főoldal (friss hírek, összefoglalók)
* keresőfelület
* cikkoldal (eredeti + fordított szöveg)
* témaböngésző
* admin felület

---

## 7. Relevancia és rangsorolás

A rendszer fejlesztésének kulcseleme a cikkek súlyozása:

* több forrásban való megjelenés
* kulcsszavak és entitások súlya
* frissesség
* témasúly
* tartalmi gazdagság

Ez javítja:

* az összefoglalók minőségét
* a keresési találatok relevanciáját
* a hírlevelek tartalmát

---

## 8. Fejlesztési fázisok

### Fázis 1

* PostgreSQL bevezetése
* teljes szövegek és fordítások mentése
* cron alapú futtatás

### Fázis 2

* tárgyszavazás
* entitáskinyerés
* alap ranking

### Fázis 3

* témamodellezés
* trendanalízis
* automatikus hírlevél

### Fázis 4

* keresőmotor
* webes UI

### Fázis 5

* intézményi funkciók
* felhasználók, mentett keresések
* automatizált riportok

---

## 9. Könyvtári alkalmazhatóság

A rendszer jól illeszkedik szakkönyvtári felhasználásra, mivel:

* többnyelvű forrásokat kezel és fordít
* támogatja a tematikus feltárást
* kereshető tudásbázist épít
* automatizálja a médiakövetést
* segíti a gyors szakmai tájékozódást

---

## 10. Összegzés

A jelenlegi rendszer egy jól működő prototípus, amely megfelelő alapot ad egy komplexebb, intézményi szinten is használható médiamegfigyelő platform kialakításához.

A továbbfejlesztés fő irányai:

* teljes szövegek és fordítások tárolása
* NLP-alapú feldolgozás
* tematikus szervezés
* kereshetőség és webes elérés

Ezek megvalósításával a rendszer egy olyan eszközzé válhat, amely egyszerre támogatja a médiakövetést, az információfeltárást és a tudásbázis-építést.
