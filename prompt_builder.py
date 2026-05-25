"""
Prompt összeállítás az Ollama számára.
"""

SYSTEM_PROMPT = """
Te egy tárgyilagos, tömör és jól strukturáló magyar nyelvű hírelemző vagy.
A feladatod, hogy a megadott híranyagból készíts jól olvasható magyar markdown összefoglalót.

Kötelező szabályok:
- Csak a megadott anyagból dolgozz, ne találj ki tényeket.
- Az összefoglaló TELJES EGÉSZÉBEN magyarul legyen – minden cím, minden mondat.
- A cikkek eredeti címe idegen nyelvű (német, angol, francia) lehet; te magyarul foglald össze.
- Ha két cikk ugyanarról szól, vond össze egy közös pontba.
- A stílus legyen semleges, világos, újságíróias.
- A végén legyen egy rövid "Mire figyeljünk a következő napokban?" rész.
""".strip()

USER_TEMPLATE = """
Az alábbi híranyag az elmúlt {window_label} időszakból származik.
A cikkek eredeti nyelven is tartalmazhatnak idegen (főleg német, angol) szövegrészeket –
ezeket is magyarul foglald össze a kimenetben.

Készíts magyar nyelvű összefoglalót az alábbi szerkezetben:

# Rövid hírösszefoglaló

## Fő témák
- 5-10 tömör pont magyarul

## Részletesebb bontás
- tematikus blokkokban, minden blokk magyarul

## Mire figyeljünk a következő napokban?
- 3-5 pont magyarul

TARTALOM:

{news_markdown}
""".strip()


def build_prompt(news_markdown: str, window_label: str) -> str:
    user_part = USER_TEMPLATE.format(
        window_label=window_label,
        news_markdown=news_markdown,
    )
    return SYSTEM_PROMPT + "\n\n" + user_part
