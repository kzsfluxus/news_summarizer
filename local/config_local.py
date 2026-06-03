"""
Lokális, modell-specifikus felülírások a Racka modellhez.

Ezt a fájlt a config.py MELLÉ kell helyezni (az alkalmazás gyökerébe).
A config.py a végén automatikusan importálja, és az itteni értékek
felülírják a modellfüggetlen alapértékeket.

Ha vissza akarsz térni az alap (Llama) működésre, töröld vagy nevezd át
ezt a fájlt – a config.py ekkor a saját alapértékeivel fut tovább.
"""

# --- Modell ---------------------------------------------------------------
# A `racka-chat` modellt a local/racka-chat.modelfile alapján kell létrehozni:
#   ollama create racka-chat -f racka-chat.modelfile
OLLAMA_MODEL = "racka-news:latest"

# --- Kontextus és hírszám -------------------------------------------------
# A Racka adaptált tokenizere a magyart hatékonyabban csomagolja, így ugyanaz
# a num_ctx több hírt fogad be, mint a Llamánál. 8 GB-os gépen a 8192 jó
# kompromisszum: nagyjából megduplázza a kapacitást, a KV-cache memóriaigénye
# (Qwen3 GQA mellett) mérsékelt marad. Nagyobb gépen óvatosan emelhető.
OLLAMA_NUM_CTX    = 8192
MAX_SUMMARY_ITEMS = 12     # Indulásnak; a saját feededen érdemes belőni

# --- Generálás ------------------------------------------------------------
# A no-think a Modelfile-ban van bekapcsolva, így itt a kimenet már a tényleges
# összefoglaló. A strukturált kimenethez (témák + bontás + előretekintés) több
# token kell, mint a Llama korábbi 700-ánál.
OLLAMA_NUM_PREDICT = 1200

# Összefoglaláshoz alacsonyabb hőmérséklet a forráshűségért. Ez megegyezik a
# Modelfile PARAMETER temperature értékével (az app-opció amúgy felülírja azt,
# ezért tartjuk szinkronban).
OLLAMA_TEMPERATURE = 0.4
