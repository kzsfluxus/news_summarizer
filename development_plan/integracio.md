# Céges / intézményi integráció – fejlesztési irányok

Ez a dokumentum azt foglalja össze, hogy az aktuális, egyfelhasználós lokális rendszer
milyen területeken fejleszthető tovább intézményi vagy céges bevezetés esetén.
Három fő tengelyen vizsgáljuk a lehetőségeket: jogosultságkezelés, NLP-minőség
és infrastrukturális skálázhatóság.

---

## 1. Jogosultságkezelés és felhasználói funkciók

Az jelenlegi rendszernek nincs hozzáférés-vezérlése: bárki, aki eléri a Flask szervert,
teljes körűen használhatja. Intézményi környezetben ez nem elfogadható.

### 1.1. Hitelesítés és szerepkörök

A beléptetési réteg minimálisan két szerepkört különböztet meg.

Az **olvasó** megtekintheti az összefoglalókat, kereshet a cikkekben, böngészheti
a témákat és letöltheti a hírleveleket, de nem futtathat pipeline-t és nem módosíthatja
a forrásokat.

Az **adminisztrátor** minden olvasói funkcióhoz hozzáfér, emellett pipeline-t indíthat,
forrásokat adhat hozzá vagy vonhat vissza, megtekintheti a job-naplókat és exportálhat.

Kibővítettebb modellben megjelenik a **szerkesztő** szerepkör is, aki manuálisan
megjelölhet cikkeket, szerkesztheti az automatikusan generált összefoglalókat,
és jóváhagyhatja a hírleveleket kiküldés előtt.

Technikai megvalósítás: Flask-Login + SQLAlchemy `users` tábla, vagy külső
identity provider (LDAP, Active Directory, OAuth2/OIDC) integrációja
Flask-OIDC-en keresztül. Intézményi környezetben az utóbbi az elterjedtebb,
mert a meglévő felhasználói adatbázist hasznosítja újra.

### 1.2. Mentett keresések és értesítések

A felhasználók el tudják menteni a keresési feltételeket (kulcsszó + szűrők kombinációja).
Rendszeres futás esetén az értesítési rendszer megvizsgálja, hogy az adott feltétel
új találatot hozott-e az előző futás óta, és e-mailben vagy belső üzenetben jelzi.

Ez a funkcó könyvtári vagy sajtófigyelési kontextusban különösen értékes: egy
referens beállíthatja, hogy kapjon értesítést minden alkalommal, amikor egy adott
szervezet neve vagy egy adott téma megjelenik az indexelt forrásokban.

### 1.3. Ütemezett automatikus futtatás

Az egyfelhasználós verzióban a pipeline manuálisan indul. Intézményi bevezetésnél
az APScheduler vagy egy külső cron konfiguráció veszi át ezt a szerepet: a pipeline
naponta egyszer vagy kétszer automatikusan lefut, az összefoglaló és a hírlevél
reggel elkészül, mire a munkatársak megnyitják a böngészőt.

### 1.4. Auditnapló

Céges GDPR-megfelelőségi és belső ellenőrzési igény esetén minden keresési lekérés,
pipeline-indítás és forrás-módosítás naplózódik egy `audit_log` táblában
(user_id, action, timestamp, details). Ez az admin felületen szűrhetően megjelenik.

### 1.5. Exportálás

Az összefoglalók és keresési találatok exportálása PDF és DOCX formátumban,
a szervezet arculati sablonjával. A hírlevél jelenleg is önálló HTML, de
intézményi bevezetésnél ez csatlakoztatható egy meglévő levélküldő rendszerhez
(Mailchimp API, SMTP relay, belső groupware) automatikus kiküldéssel.

---

## 2. NLP-minőség: a TF-IDF utáni lépések

A jelenlegi témamodellezés TF-IDF + cosine similarity alapú, ami gyors és offline,
de szóalak-szintű: csak akkor rak össze két cikket, ha közös tokenjeik vannak.
Következménye, hogy szinonimák, névváltozatok és többnyelvű tartalmak széteshetnek
különböző klaszterekbe akkor is, ha valójában ugyanarról szólnak.

### 2.1. Szemantikus témamodellezés BERTopic-kal

A BERTopic a sentence-transformers által generált mondatvektorokat UMAP-pal
csökkenti alacsonyabb dimenzióba, majd HDBSCAN-nal klaszterezi. Eredmény:
szemantikusan összetartozó cikkek akkor is egy témába kerülnek, ha eltérő szavakat
használnak – ez különösen fontos a rendszer többnyelvű forrásai esetén, ahol egy
eseményről egyszerre érkezhetnek magyar, angol és német szövegek.

A BERTopic meghatározza az optimális klaszterszámot automatikusan, nem szükséges
előre megadni; és képes a „zaj" kategóriát is kezelni (egyedi, semmilyen témába
nem illő cikkek).

Bevezetési feltétel: a sentence-transformers modell már telepítve van a KeyBERT
miatt, tehát a tényleges pluszköltség az UMAP és HDBSCAN csomag, valamint
a megnövekedett futási idő (CPU-n ~2–5× lassabb a TF-IDF-nél, GPU-n hasonló).

### 2.2. Fejlettebb entitáskinyerés és entitásegyesítés

A jelenlegi GLiNER modell felismeri az entitásokat, de nem oldja fel a névvariánsokat:
„Orbán Viktor", „Orbán", „Viktor Orbán" és „a miniszterelnök" négy különböző
entitásként szerepel a panelen.

Intézményi bevezetésnél érdemes egy entitásegyesítési réteget (entity resolution)
hozzáadni: ez lehet egy egyszerű fuzzy-matching alapú normalizáció
(rapidfuzz könyvtárral), vagy egy tudásbázishoz kötött feloldás
(Wikidata API, DBpedia spotlight).

Az eredmény: az entitáspanelen „Orbán Viktor" egyetlen rekordként jelenik meg
az összes névvariáns előfordulásszámával, és a keresés is egységesen talál rá.

### 2.3. Összefoglaló-minőség: nagyobb vagy finomhangolt modell

A jelenlegi Ollama modell (`llama3.2:3b`) 3 milliárd paraméteres, ami CPU-n is fut,
de a kimeneti minőség korlátozott: vegyes nyelvű bemenetnél előfordulhat, hogy az
összefoglaló részben átveszi az eredeti idegen nyelvű szövegrészeket.

Intézményi szerveren, ahol GPU áll rendelkezésre, érdemes átváltani egy nagyobb
modellre: a `llama3.1:8b` vagy a `mistral:7b` lényegesen jobb instrukció-követési
képességgel rendelkezik, és a „csak magyarul válaszolj" utasítást megbízhatóbban
tartja be. A váltás a `config.py` egyetlen sorát érinti (`OLLAMA_MODEL`).

Ha a szervezetnek saját terminológiája van (pl. belső szakkifejezések, projektek
nevei), a modell finomhangolható LoRA adapterrel az intézményi szövegkorpuszon,
ami tovább javítja a relevanciát.

### 2.4. Relációkinyerés

Az entitáskinyerés után következő természetes lépés a relációkinyerés:
nemcsak azt rögzítjük, hogy egy szövegben megjelenik „Orbán Viktor" és „Brüsszel",
hanem azt is, hogy milyen kapcsolatban állnak (tárgyalás, kritika, egyezmény stb.).
Ez grafalapú tudásbázis-építést tesz lehetővé, ami a keresési és összefoglalási
minőséget egyaránt emeli.

---

## 3. Infrastrukturális skálázhatóság: SQLite → PostgreSQL

### 3.1. Mikor nem elég a SQLite

A SQLite kiválóan működik egyfelhasználós, soros írásokkal járó esetekben.
Három szituációban válik szűk keresztmetszetté:

**Egyidejű írások.** A SQLite fájlszintű zárolást alkalmaz: ha egyszerre fut
a pipeline (ami írja az articles táblát) és egy felhasználó a keresőoldalon
tallóz (ami olvas), ez általában rendben van. De ha több párhuzamos pipeline-fut,
vagy több webszerver-worker indulna el (pl. gunicorn több worker-rel), az írási
zárolások versenyhelyzethez és `database is locked` hibákhoz vezetnek.

**Nagy adatmennyiség.** Néhány tízezer cikk után a SQLite FTS5 keresési ideje
érzékelhetően nő; a PostgreSQL `tsvector` + GIN index ennél lényegesen jobban
skálázódik, és lehetővé teszi a szótövezést (magyar stemmer) is.

**Több intézményi node.** Ha a rendszer több helyszínen fut (pl. könyvtárhálózat
fióktelepei), a megosztott PostgreSQL szerver egységes adatbázist jelent
az összes csomópont számára. SQLite-on ez nem megoldható.

### 3.2. A migráció mértéke

A séma struktúra változatlan marad, a táblák és indexek átvihetők.
A konkrét változások:

Az FTS5 virtuális tábla helyére `tsvector` oszlopok és GIN indexek kerülnek
az `articles` táblában. A triggerek megmaradnak, de PostgreSQL szintaxissal.
A `tsquery` lehetővé teszi a szótő-alapú keresést, ami a magyar szövegeken
(ragozás) jobban teljesít, mint az FTS5 token-egyezés.

A `db_service.py`-ban az SQLite-specifikus `sqlite3` modul helyére
SQLAlchemy + psycopg2 kerül; a lekérdezések nagy részén nem kell változtatni,
mert a SQL dialektus kompatibilis. A `PRAGMA table_info` és az `executescript`
hívások igényelnek átírást.

A `connection pooling` kezelése PostgreSQL esetén az alkalmazás szintjén is
megvalósul (SQLAlchemy pool), ami gunicorn multi-worker esetén is biztonságos.

### 3.3. Teljesítménybecslés

Egy tipikus intézményi példán (napi 200–500 új cikk, 50 000 cikk összesen,
5–10 egyidejű felhasználó) a PostgreSQL a következő előnyöket hozza a SQLite-hoz
képest:

A keresési idő 0.1–0.5 másodpercről 0.02–0.1 másodpercre csökken GIN index
és tsvector esetén. Az egyidejű írás-olvasás ütközések megszűnnek (MVCC modell).
A napi pipeline futási ideje nem változik érdemben, mert ez CPU-korlátozott
(NLP lépések), nem I/O-korlátozott.

### 3.4. Deployment architektúra intézményi bevezetésnél

A legegyszerűbb intézményi architektúra: egyetlen szerver, amelyen fut
a Flask alkalmazás gunicorn mögött, egy Nginx reverse proxy,
és egy helyi PostgreSQL példány. Ez kb. 4–8 magos, 16 GB RAM-os szerveren
kényelmesen kiszolgál 20–50 egyidejű felhasználót.

Ha a rendelkezésre álló GPU-t az Ollama foglalja (nagy modell futtatásához),
az NLP modellek (GLiNER, KeyBERT) CPU-n futnak párhuzamosan –
ehhez legalább 8 mag ajánlott a pipeline ésszerű futási idejéhez.

Konténerizált bevezetésnél (Docker Compose vagy Kubernetes) a Flask alkalmazás,
a PostgreSQL és az Ollama szerver külön konténerben fut; a pipeline-t
egy dedikált worker konténer kezeli, ami leválasztja a nehéz NLP számítást
a webszerver rendelkezésre állásáról.

---

## 4. Összefoglalás

| Terület | Jelenlegi állapot | Intézményi szint |
|---|---|---|
| Hozzáférés | Nincs hitelesítés | Szerepkör-alapú (olvasó / szerkesztő / admin) |
| Értesítések | Nincs | Mentett keresések + e-mail / groupware push |
| Futtatás | Manuális | Ütemezett, automatikus (APScheduler / cron) |
| Export | HTML hírlevél | PDF, DOCX, levélküldő integráció |
| Témamodellezés | TF-IDF (szóalak) | BERTopic (szemantikus, GPU-n gyors) |
| Entitásegyesítés | Nincs | Fuzzy matching / Wikidata feloldás |
| Összefoglaló modell | llama3.2:3b | llama3.1:8b vagy finomhangolt modell |
| Adatbázis | SQLite (egyszálú írás) | PostgreSQL (MVCC, tsvector, connection pool) |
| Keresés | FTS5 BM25 | PostgreSQL tsvector + GIN + magyar stemmer |
| Deployment | Lokális Flask | Gunicorn + Nginx, Docker / Kubernetes opció |
