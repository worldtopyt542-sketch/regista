# ==== COMUNE: percorsi, stato, brand kit, lingue, didascalie, gruppi di clip pronte ====
# Il "prodotto" e' replicabile: per un nuovo canale si cambia solo il blocco "brand" (+ assets) in config.json.
import datetime, json, os, secrets

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(RADICE, "config.json")
ARCHIVIO = os.path.join(RADICE, "archivio.json")
PRONTE = os.path.join(RADICE, "pronte")  # un file per gruppo di clip (scritto da clipper/fatti, letto da pubblica)

BOTTONI = [[{"text": "✅ Pubblica", "callback_data": "ok"}, {"text": "❌ Scarta", "callback_data": "no"}]]


def carica(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def salva(path, dati):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, indent=1)


BRAND_BASE = {
    "nome": "Planet Off Scale",
    "handle": "@planetoffscale",
    "colore": "#FFD400",
    "logo_video": "assets/logo_video.png",
    "font": "Inter Display Black",
    "nicchia": "viral videos",
    "tono": "awe-struck documentary narrator: short, vivid, factual sentences",
    "hashtag_fissi": ["#shorts"],
    "cta": {"en": "FOLLOW FOR MORE"},
}


def brand(cfg=None):
    cfg = carica(CONFIG, {}) if cfg is None else cfg
    return {**BRAND_BASE, **(cfg.get("brand") or {})}


def lingue(cfg):
    return cfg.get("lingue") or {"en": {"nome": "English", "voce": "en-US-GuyNeural"}}


def cta(cod, cfg=None):
    c = brand(cfg)["cta"]
    return c.get(cod) or c.get("en") or ""


def hashtag(t, cfg=None):
    """Hashtag del video + quelli fissi del brand, senza doppioni."""
    tags = list(t.get("hashtags") or []) + brand(cfg)["hashtag_fissi"]
    return list(dict.fromkeys("#" + h.lstrip("#").replace(" ", "") for h in tags if h.strip("# ")))[:8]


def attribuzione(fonte):
    """Riga di credito per il post. CC BY chiede: autore, link alla fonte, licenza, e che e' stato modificato."""
    if not fonte:
        return ""
    lic, aut, url = fonte.get("licenza", ""), fonte.get("autore", ""), fonte.get("url", "")
    if lic == "CC BY":
        return f"🎥 Original: \"{fonte.get('titolo', '')[:80]}\" by {aut} — {url}\nLicense: CC BY 4.0 (creativecommons.org/licenses/by/4.0) · edited (cut, captions, music levels)"
    if lic == "Public domain":
        return f"🎥 Footage: {aut} (public domain){' — ' + url if url else ''}" + \
               ("\nNASA does not endorse this channel." if "NASA" in aut else "")
    return f"🎥 Footage: {aut}{' — ' + url if url else ''}"


def didascalia(t, cod, credito, extra=""):
    """Testo che accompagna il video su Telegram (per chi approva). Il Pubblicatore usa il file del gruppo."""
    return (f"{t['titolo']}\n\n{t.get('descrizione', '')}\n\n{' '.join(hashtag(t))}\n\n"
            f"🔥 {extra} · {cod.upper()} · Credit: {credito}")[:1000]


def nuovo_gruppo():
    return datetime.datetime.utcnow().strftime("%y%m%d%H%M") + secrets.token_hex(2)


def salva_gruppo(g):
    """Ogni gruppo e' un file nuovo: nessun conflitto git fra i workflow che producono e quello che pubblica."""
    salva(os.path.join(PRONTE, g["id"] + ".json"), g)


def gruppi():
    if not os.path.isdir(PRONTE):
        return {}
    out = {}
    for f in sorted(os.listdir(PRONTE)):
        if f.endswith(".json"):
            g = carica(os.path.join(PRONTE, f), None)
            if g and g.get("id"):
                out[g["id"]] = g
    return out


def pulisci_gruppi(giorni=21):
    """Chi produce cancella i propri gruppi vecchi (il Pubblicatore non scrive mai in pronte/)."""
    if not os.path.isdir(PRONTE):
        return
    limite = datetime.datetime.utcnow() - datetime.timedelta(days=giorni)
    for f in os.listdir(PRONTE):
        p = os.path.join(PRONTE, f)
        g = carica(p, {}) if f.endswith(".json") else {}
        try:
            if datetime.datetime.fromisoformat(g.get("creato", "")) < limite:
                os.remove(p)
        except ValueError:
            pass


def soglia_auto(cfg):
    """Punteggio sopra il quale un gruppo va in programma senza ✅ (None = sempre approvazione manuale)."""
    s = (cfg.get("pubblica") or {}).get("auto_pubblica_sopra")
    return None if s in (None, "", 0) else int(s)
