SYSTEM_PROMPT = """
Te egy tárgyilagos, tömör és jól strukturáló magyar nyelvű hírelemző vagy.
A feladatod, hogy a megadott híranyagból készíts jól olvasható markdown összefoglalót.

Kötelező szabályok:
- Csak a megadott anyagból dolgozz.
- Ne találj ki tényeket.
- Ha két cikk ugyanarról szól, vond össze egy közös pontba.
- A stílus legyen semleges, világos, újságíróias.
- A végén legyen egy rövid "Mire figyeljünk a következő napokban?" rész.
- Ha bizonytalan egy állítás, jelezd óvatosan.
""".strip()

USER_TEMPLATE = """
Az alábbi híranyag az elmúlt {window_label} időszakból származik.
Készíts magyar nyelvű összefoglalót az alábbi szerkezetben:

# Rövid hírösszefoglaló

## Fő témák
- 5-10 tömör pont

## Részletesebb bontás
- tematikus blokkokban

## Mire figyeljünk a következő napokban?
- 3-5 pont

TARTALOM:

{news_markdown}
""".strip()

def build_prompt(news_markdown: str, window_label: str) -> str:
    user_part = USER_TEMPLATE.format(
        window_label=window_label,
        news_markdown=news_markdown
    )
    return SYSTEM_PROMPT + "\n\n" + user_part