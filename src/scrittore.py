# ==== AGENT SCENEGGIATORE + chiamate Gemini (piano gratuito) ====
# scrivi(): copione del format "Off Scale Facts" (5 fatti fuori scala, voce narrante, filmati NASA / Pixabay).
import json, re, urllib.parse, urllib.request

BASE = "https://generativelanguage.googleapis.com/v1beta/"

PROMPT = """You write scripts for "{brand}", a viral YouTube Shorts / TikTok / Reels channel: {nicchia}.
Format "Off Scale Facts": a Top 5 countdown of mind-blowing, REAL facts about one theme, narrated over real footage.
Narrator voice: {tono}.

Theme for today: {tema}
Do NOT repeat any of these already-published titles: {gia_fatti}
{spunti}

Rules:
- Only well-established facts (NASA, ESA, NOAA, National Geographic, peer-reviewed science). No myths, no rumours.
  Prefer facts with a striking NUMBER or COMPARISON of scale ("big enough to fit 1,300 Earths").
- Total spoken text 55-65 words, NEVER more than 70 (25-30 seconds). Short, punchy sentences.
- Hook: max 14 words, a surprising statement or question about scale.
- Each item: max 12 words. Finale: max 10 words, a twist or a question that makes people comment.
- For each item one footage search query (2-4 plain English words) that a stock/NASA library can match,
  e.g. "solar flare", "humpback whale", "rocket launch night". No brand names.
- "fonte": "nasa" for space/Earth-from-orbit footage, "stock" for animals, nature, weather, oceans.
- "verifica": one public URL (nasa.gov, esa.int, noaa.gov, nationalgeographic.com, britannica.com...) that supports the fact.
- "descrizione": one catchy sentence for the post.

Reply with JSON only, no markdown:
{{"titolo": "...", "descrizione": "...", "hook": "...", "hook_query": "...", "hook_fonte": "nasa",
 "items": [{{"label": "#5", "testo": "...", "query": "...", "fonte": "stock", "verifica": "..."}},
           ... down to "#1"],
 "finale": "...", "finale_query": "...", "finale_fonte": "nasa",
 "hashtags": ["#space", "..."]}}
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


ULTIMO_BUONO = None  # il modello che ha funzionato, provato per primo al video successivo
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
    i = testo.find("{")
    return json.JSONDecoder().raw_decode(testo[i:])[0]  # ignora testo extra dopo il JSON


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
    if not 45 <= parole <= 72:
        errori.append(f"{parole} parole (obiettivo 55-65)")
    return errori


def scrivi(chiave, tema, gia_fatti, modello="auto", tentativi=3, spunti=None, brand=None):
    brand = brand or {}
    testo_spunti = ""
    if spunti:
        testo_spunti += ("\nTrending on YouTube right now for this theme (use ONLY as inspiration for the angle; "
                        "never copy titles, never mention channels): " + " | ".join(spunti[:3]))
    prompt = PROMPT.format(brand=brand.get("nome", "Planet Off Scale"), nicchia=brand.get("nicchia", ""),
                           tono=brand.get("tono", ""), tema=tema, gia_fatti="; ".join(gia_fatti[-60:]) or "none", spunti=testo_spunti)
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.9, "responseMimeType": "application/json"}}
    global ULTIMO_BUONO
    candidati = modelli_candidati(chiave, ULTIMO_BUONO or (None if modello == "auto" else modello))
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
                testo = "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"])
                s = estrai_json(testo)
            except Exception as e:
                problemi.append(f"{m}: risposta non leggibile")
                continue
            errori = valida(s)
            if s.get("titolo", "").strip().lower() in {g.strip().lower() for g in gia_fatti}:
                errori.append("titolo gia' pubblicato")
            if not errori:
                print(f"   Sceneggiatore: script scritto con {m}")
                ULTIMO_BUONO = m
                s["items"] = sorted(s["items"], key=lambda it: -int(re.sub(r"\D", "", it.get("label", "0")) or 0))
                return s
            problemi.append(f"{m}: " + "; ".join(errori))
            print(f"   Sceneggiatore: tentativo {t + 1} con {m} scartato ({'; '.join(errori)})")
    raise RuntimeError("Sceneggiatore: nessun modello ha funzionato. " + " | ".join(problemi[-6:]))


def gemini(chiave, prompt, temp=0.5, immagini=None):
    """Chiamata JSON generica (con fotogrammi jpg facoltativi): prova i modelli flash finche' uno risponde."""
    import base64
    global ULTIMO_BUONO
    parti = [{"text": prompt}]
    for etichetta, path in immagini or []:
        parti.append({"text": etichetta})
        parti.append({"inline_data": {"mime_type": "image/jpeg",
                                      "data": base64.b64encode(open(path, "rb").read()).decode()}})
    body = {"contents": [{"parts": parti}],
            "generationConfig": {"temperature": temp, "responseMimeType": "application/json"}}
    import time
    errori = []
    for giro in range(6):  # piano gratuito: limiti al minuto (429) e sovraccarichi (503) -> aspetta e riprova
        for m in modelli_candidati(chiave, ULTIMO_BUONO):
            try:
                r = _post(f"{BASE}models/{m}:generateContent?key={urllib.parse.quote(chiave)}", body)
                out = estrai_json("".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"]))
                ULTIMO_BUONO = m
                return out
            except Exception as e:
                errori.append(f"{m}: {str(e)[:80]}")
        attesa = min(60 * (giro + 1), 180)
        print(f"   Gemini: nessun modello libero, attendo {attesa} s (giro {giro + 1}/6)")
        time.sleep(attesa)
    raise RuntimeError("Gemini non risponde: " + " | ".join(errori[-3:]))


def traduci(chiave, dati, lingue):
    """dati: dict in inglese. lingue: {codice: nome}. Ritorna {codice: dict tradotto} (inglese se fallisce)."""
    if not lingue:
        return {}
    prompt = ("Translate every string value of this JSON into each target language. Keep keys and list lengths "
              "IDENTICAL. Sound native and viral on Shorts/TikTok for that country, not literal. Keep proper names "
              "(NASA, SpaceX, place and species names as locals say them), numbers and units converted only if "
              "locals use other units. Localize hashtags. Keep each string about as short as the original "
              "(subtitles must fit on screen).\n"
              "Target languages: " + ", ".join(f'"{k}" = {v}' for k, v in lingue.items()) +
              '\nReply JSON only: {"<code>": <translated JSON>, ...}\n\n' + json.dumps(dati, ensure_ascii=False))
    try:
        t = gemini(chiave, prompt, 0.4)
    except Exception as e:
        print("   Traduttore:", e)
        t = {}
    out = {}
    for k in lingue:
        v = t.get(k)
        ok = isinstance(v, dict) and all(
            (len(v.get(c) or []) == len(dati[c])) if isinstance(dati[c], list) else bool(v.get(c)) for c in dati)
        out[k] = v if ok else dati
        if not ok:
            print(f"   Traduttore: {k} non valido, uso l'inglese")
    return out
