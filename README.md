# Hírösszefoglaló

Ez a verzió otthoni használatra van hangolva:

- SQLite alapú helyi tárolás
- URL-szintű cache
- tartalmi hash alapú duplikátumszűrés
- háttérszálas pipeline
- automatikus Ollama indítás subprocessként, ha még nem fut
- automatikus leállítás, ha az alkalmazás indította el
- chunkolt fordítás
- `news.md`, `summary.html`, `news.db` kimenetek

## Könyvtárstruktúra

```text
news_summarizer_v3/
├── app.py
├── config.py
├── feeds.yaml
├── prompt_builder.py
├── requirements.txt
├── output/
│   ├── jobs/
│   ├── news.db
│   ├── news.md
│   └── summary.html
├── services/
│   ├── __init__.py
│   ├── db_service.py
│   ├── feed_service.py
│   ├── scrape_service.py
│   ├── translate_service.py
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
pip3 install -r requirements.txt
python app.py
```

A felület:

```text
http://127.0.0.1:5000
```

## Fontos működési elv

### Ollama kezelés

- ha az Ollama már fut a `127.0.0.1:11434` címen, a program azt használja
- ha nem fut, megpróbálja elindítani `ollama serve` paranccsal
- a feldolgozás végén csak akkor állítja le, ha ő indította el

## SQLite cache

A `news.db` adatbázisban tároljuk:

- a letöltött és feldolgozott cikkeket
- a magyar fordítást
- a mini magyar kivonatot
- a végső összefoglalókat

Ennek előnye:

- ugyanazt az URL-t nem kell újra scrape-elni
- a végső összefoglaló már korábban letárolt cikkekből is összeállítható
- új időablaknál csak az új cikkek töltődnek le

## Korlátok

- a mini összefoglaló itt még egyszerű, extraktív kivonat
- a fordítás `deep-translator` alapú
- a tartalmi duplikátumszűrés heurisztikus
- nincs témaszűrés vagy ranking

