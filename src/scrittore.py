# ==== AGENT SCENEGGIATORE: scrive una Top 5 con Gemini (piano gratuito) ====
import json, re, urllib.parse, urllib.request

BASE = "https://generativelanguage.googleapis.com/v1beta/"

PROMPT = """You write scripts for a YouTube Shorts channel called "Planet Off Scale":
Top 5 rankings of the most extreme, real phenomena on Earth and in space.

Theme for today: {tema}
Do NOT repeat any of these already-published titles: {gia_fatti}
{spunti}

Rules:
- Only well-documented, verifiable facts. If unsure of a number or date, leave it out.
- Total spoken text 60-75 words (about 25-30 seconds). Short, punchy sentences.
- Hook: max 14 words, a surprising statement or question.
- Each item: max 12 words, starts with the place or year when it helps.
- For each item give one English search query (2-4 words) describing footage that a
  stock or NASA archive would have (e.g. "volcano lava flow", "aurora from space").
- "fonte": "nasa" for space/Earth-from-orbit footage, otherwise "stock".
- "verifica": one public URL (Wikipedia or an official agency) that supports the fact.

Reply with JSON only, no markdown:
{{"titolo": "...", "hook": "...", "hook_query": "...", "hook_fonte": "nasa|pexels",
 "items": [{{"label": "#5", "testo": "...", "query": "...", "fonte": "...", "verifica": "..."}},
           ... down to "#1"],
 "finale": "...", "finale_query": "...", "finale_fonte": "...",
 "hashtags": ["#shorts", "..."]}}
"""


def _post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=150) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Gemini HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:300]}")
    except (TimeoutError, OSError) as e:  # nessuna risposta in tempo o rete interrotta
        raise RuntimeError(f"Gemini HTTP 408: nessuna risposta ({e})")


ESCLUSI = ("image", "tts", "live", "omni", "audio", "embedding", "vision", "learnlm")


def modelli_candidati(chiave, preferito=None):
    """Tutti i modelli Gemini 'flash' utilizzabili: prima gli stabili, versione piu' recente prima."""
    with urllib.request.urlopen(BASE + "models?pageSize=200&key=" + urllib.parse.quote(chiave), timeout=60) as r:
        modelli = json.loads(r.read().decode()).get("models", [])
    nomi = [m["name"].split("/")[-1] for m in modelli
            if "generateContent" in m.get("supportedGenerationMethods", [])]
    flash = [n for n in nomi if n.startswith("gemini") and "flash" in n and not any(x in n for x in ESCLUSI)]

    def chiave_ordine(n):
        v = re.search(r"gemini-(\d+(?:\.\d+)?)", n)
        versione = float(v.group(1)) if v else 0
        instabile = any(x in n for x in ("preview", "exp", "thinking"))
        return (instabile, -versione, "lite" in n, n)

    flash.sort(key=chiave_ordine)
    if preferito and preferito in flash:
        flash.remove(preferito)
        flash.insert(0, preferito)
    return flash


def estrai_json(testo):
    testo = testo.strip()
    testo = re.sub(r"^```(?:json)?|```$", "", testo, flags=re.M).strip()
    i, j = testo.find("{"), testo.rfind("}")
    return json.loads(testo[i:j + 1])


def valida(s):
    errori = []
    for k in ("titolo", "hook", "hook_query", "items", "finale"):
        if not s.get(k):
            errori.append(f"manca '{k}'")
    items = s.get("items", [])
    if len(items) != 5:
        errori.append(f"{len(items)} voci invece di 5")
    for it in items:
        if not it.get("testo") or not it.get("query"):
            errori.append("voce senza testo o query")
    parole = len(s.get("hook", "").split()) + len(s.get("finale", "").split()) + \
        sum(len(it.get("testo", "").split()) for it in items)
    if not 45 <= parole <= 95:
        errori.append(f"{parole} parole (obiettivo 60-75)")
    return errori


def scrivi(chiave, tema, gia_fatti, modello="auto", tentativi=3, spunti=None):
    testo_spunti = ""
    if spunti:
        testo_spunti = ("Trending on YouTube right now for this theme (use ONLY as inspiration for the angle; "
                        "never copy titles, never mention channels): " + " | ".join(spunti[:3]))
    prompt = PROMPT.format(tema=tema, gia_fatti="; ".join(gia_fatti[-60:]) or "none", spunti=testo_spunti)
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.9, "responseMimeType": "application/json"}}
    candidati = modelli_candidati(chiave, None if modello == "auto" else modello)
    if not candidati:
        raise RuntimeError("Nessun modello Gemini 'flash' disponibile per questa chiave")
    problemi = []
    for m in candidati:
        for t in range(tentativi):
            print(f"   Sceneggiatore: provo {m}")
            try:
                r = _post(f"{BASE}models/{m}:generateContent?key={urllib.parse.quote(chiave)}", body)
            except RuntimeError as e:
                codice = str(e)[12:15]
                if codice in ("429", "404", "403", "400", "408", "500", "503"):
                    problemi.append(f"{m}: HTTP {codice}")
                    print(f"   Sceneggiatore: {m} non utilizzabile (HTTP {codice}), provo il successivo")
                    break
                raise
            try:
                testo = r["candidates"][0]["content"]["parts"][0]["text"]
                s = estrai_json(testo)
            except Exception as e:
                problemi.append(f"{m}: risposta non leggibile")
                continue
            errori = valida(s)
            if s.get("titolo", "").strip().lower() in {g.strip().lower() for g in gia_fatti}:
                errori.append("titolo gia' pubblicato")
            if not errori:
                print(f"   Sceneggiatore: script scritto con {m}")
                s["items"] = sorted(s["items"], key=lambda it: -int(re.sub(r"\D", "", it.get("label", "0")) or 0))
                return s
            problemi.append(f"{m}: " + "; ".join(errori))
            print(f"   Sceneggiatore: tentativo {t + 1} con {m} scartato ({'; '.join(errori)})")
    raise RuntimeError("Sceneggiatore: nessun modello ha funzionato. " + " | ".join(problemi[-6:]))
