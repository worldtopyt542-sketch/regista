# ==== AGENT SCENEGGIATORE: scrive una Top 5 con Gemini (piano gratuito) ====
import json, re, urllib.parse, urllib.request

BASE = "https://generativelanguage.googleapis.com/v1beta/"

PROMPT = """You write scripts for a viral YouTube Shorts / TikTok channel about GTA 6 (Grand Theft Auto VI,
released November 19, 2026). Format: Top 5 news, secrets, tips or facts. Base news on the LATEST HEADLINES below when relevant.

Theme for today: {tema}
Do NOT repeat any of these already-published titles: {gia_fatti}
{spunti}

Rules:
- Only verifiable facts (official Rockstar info, reliable gaming press). No story spoilers. No invented leaks.
- Total spoken text 55-65 words, NEVER more than 70 (25-30 seconds). Short, punchy sentences, gamer tone.
- Hook: max 14 words, a surprising statement or question.
- Each item: max 10 words.
- For each item one YouTube search query (2-5 words) for matching GTA 6 gameplay footage, e.g. "Vice City beach", "police chase". Do not include "GTA 6" in it.
- "fonte": always "gameplay".
- "verifica": one public URL that supports the fact.
- "descrizione": one catchy sentence for the post.

Reply with JSON only, no markdown:
{{"titolo": "...", "descrizione": "...", "hook": "...", "hook_query": "...", "hook_fonte": "gameplay",
 "items": [{{"label": "#5", "testo": "...", "query": "...", "fonte": "gameplay", "verifica": "..."}},
           ... down to "#1"],
 "finale": "...", "finale_query": "...", "finale_fonte": "gameplay",
 "hashtags": ["#gta6", "..."]}}
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


def notizie(query="GTA 6", quante=15):
    """Ultimi titoli da Google News (RSS gratuito), per avere fatti freschi senza grounding a pagamento."""
    import xml.etree.ElementTree as ET
    try:
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
            {"q": query + " when:3d", "hl": "en-US", "gl": "US", "ceid": "US:en"})
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            items = ET.fromstring(r.read()).iter("item")
            righe = [f"- {i.findtext('title')} ({i.findtext('link')})" for _, i in zip(range(quante), items)]
        return "LATEST HEADLINES (last 3 days):\n" + "\n".join(righe) if righe else ""
    except Exception as e:
        print("   Notizie: RSS non disponibile", e)
        return ""


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
    if not 45 <= parole <= 72:
        errori.append(f"{parole} parole (obiettivo 55-65)")
    return errori


def scrivi(chiave, tema, gia_fatti, modello="auto", tentativi=3, spunti=None):
    testo_spunti = notizie()
    if spunti:
        testo_spunti += ("\nTrending on YouTube right now for this theme (use ONLY as inspiration for the angle; "
                        "never copy titles, never mention channels): " + " | ".join(spunti[:3]))
    prompt = PROMPT.format(tema=tema, gia_fatti="; ".join(gia_fatti[-60:]) or "none", spunti=testo_spunti)
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


def gemini(chiave, prompt, temp=0.5):
    """Chiamata JSON generica: prova i modelli flash finche' uno risponde."""
    global ULTIMO_BUONO
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temp, "responseMimeType": "application/json"}}
    errori = []
    for m in modelli_candidati(chiave, ULTIMO_BUONO):
        try:
            r = _post(f"{BASE}models/{m}:generateContent?key={urllib.parse.quote(chiave)}", body)
            out = estrai_json("".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"]))
            ULTIMO_BUONO = m
            return out
        except Exception as e:
            errori.append(f"{m}: {str(e)[:80]}")
    raise RuntimeError("Gemini non risponde: " + " | ".join(errori[-3:]))


def traduci(chiave, dati, lingue):
    """dati: dict in inglese. lingue: {codice: nome}. Ritorna {codice: dict tradotto} (inglese se fallisce)."""
    prompt = ("Translate every string value of this JSON into each target language. Keep keys and list lengths "
              "IDENTICAL. Sound native and viral for young gamers (slang ok), not literal. Keep names (GTA 6, "
              "Vice City, streamer names). Localize hashtags but keep #gta6. Keep each string about as short as the original.\n"
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
