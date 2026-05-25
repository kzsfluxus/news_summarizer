from __future__ import annotations

from deep_translator import GoogleTranslator

TARGET_LANG = "hu"
SUPPORTED = {"hu", "en", "de", "fr"}


def chunk_text(text: str, chunk_size: int = 3500) -> list[str]:
    text = text.strip()
    if not text:
        return []
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            # rfind az [start:end] ablakban keres, nem a teljes szövegben
            split_pos = text.rfind("\n", start, end)
            if split_pos <= start:
                split_pos = text.rfind(" ", start, end)
            if split_pos > start:
                end = split_pos
        parts.append(text[start:end].strip())
        start = end
    return [p for p in parts if p]


def maybe_translate(text: str, source_lang: str, chunk_size: int = 3500) -> str:
    if not text.strip():
        return ""
    if source_lang == "hu" or source_lang not in SUPPORTED:
        return text

    translator = GoogleTranslator(source=source_lang, target=TARGET_LANG)
    translated_parts: list[str] = []
    for part in chunk_text(text, chunk_size=chunk_size):
        try:
            translated_parts.append(translator.translate(part))
        except Exception:
            translated_parts.append(part)
    return "\n\n".join(translated_parts).strip()
