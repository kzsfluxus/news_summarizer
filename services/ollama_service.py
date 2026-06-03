from __future__ import annotations

import re
import subprocess
import time
from typing import Optional

import requests

from config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_START_TIMEOUT,
    OLLAMA_URL,
    OLLAMA_WAIT_SECONDS,
    REQUEST_TIMEOUT,
    OLLAMA_TEMPERATURE,
    OLLAMA_NUM_PREDICT,
    OLLAMA_NUM_CTX,
    OLLAMA_KEEP_ALIVE,
)


class OllamaProcessError(RuntimeError):
    pass


# Reasoning modellek (pl. Qwen3 / Racka) <think>...</think> blokkot tehetnek
# a válasz elé. Ezt univerzálisan, utólag eltávolítjuk. Nem-reasoning modellnél
# (Llama, Mistral, Gemma) ez no-op: nincs mire illeszkedjen, a szöveg változatlan.
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_thinking(text: str) -> str:
    """
    Kiszedi a <think>...</think> blokkot, ha van. Csak akkor nyúl a szöveghez,
    ha ténylegesen tartalmaz nyitó taget, így a nem gondolkodó modellek
    kimenetét érintetlenül hagyja.
    """
    if "<think>" not in text.lower():
        return text
    return _THINK_RE.sub("", text).strip()


def _healthcheck() -> bool:
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        return response.ok
    except Exception:
        return False


def ensure_ollama() -> Optional[subprocess.Popen]:
    """
    Elindítja az `ollama serve` folyamatot, ha még nem fut.
    Ha már fut, None-t ad vissza.
    """
    if _healthcheck():
        return None

    proc = subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    deadline = time.time() + OLLAMA_START_TIMEOUT
    while time.time() < deadline:
        if _healthcheck():
            return proc
        time.sleep(OLLAMA_WAIT_SECONDS)

    try:
        proc.terminate()
    except Exception:
        pass

    raise OllamaProcessError("Az Ollama nem indult el időben.")


def stop_ollama(proc: Optional[subprocess.Popen]) -> None:
    """
    Csak azt a serve folyamatot állítja le, amit ez a program indított.
    """
    if proc is None:
        return

    if proc.poll() is not None:
        return

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


def unload_model(model: str = OLLAMA_MODEL, url: str = OLLAMA_URL) -> None:
    """
    Megpróbálja kirakni a modellt a memóriából.
    Ez akkor is hasznos, ha az Ollama szerver futva marad.
    """
    try:
        requests.post(
            url,
            json={
                "model": model,
                "prompt": "",
                "stream": False,
                "keep_alive": 0,
            },
            timeout=10,
        )
    except Exception:
        pass


def run_ollama(prompt: str, model: str = OLLAMA_MODEL, url: str = OLLAMA_URL) -> str:
    """
    Lefuttatja a modellt egyszeri generálásra.
    A keep_alive=0 miatt a modell a válasz után kikerül a memóriából.

    Csak univerzális opciókat küld (temperature, num_predict, num_ctx), így
    bármely modellel működik. A num_ctx explicit megadása megakadályozza, hogy
    az Ollama a rejtett 4096-os alapértékre csonkolja a promptot.
    A válaszból utólag eltávolítjuk az esetleges <think> blokkot.
    """
    response = requests.post(
        url,
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": OLLAMA_KEEP_ALIVE,
            "options": {
                "temperature": OLLAMA_TEMPERATURE,
                "num_predict": OLLAMA_NUM_PREDICT,
                "num_ctx": OLLAMA_NUM_CTX,
            },
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    result = response.json().get("response", "")
    return _strip_thinking(result.strip())
