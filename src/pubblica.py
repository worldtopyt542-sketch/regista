# ==== AGENT PUBBLICATORE + PROGRAMMATORE + REPORT ====
# Ogni 15 min: legge Telegram (link -> coda, ✅ -> programma nel prossimo orario migliore della lingua),
# pubblica quelli scaduti via Upload-Post, alle 20 UTC manda il report del giorno.
import datetime as dt, json, os, re, sys, tempfile
from zoneinfo import ZoneInfo
import requests

sys.path.insert(0, os.path.dirname(__file__))
from regista import CONFIG, RADICE, carica, salva

STATO = os.path.join(RADICE, "pubblica.json")
TG = "https://api.telegram.org/bot{t}/{m}"
URL_RE = re.compile(r"https?://\S+")
YT_RE = re.compile(r"(?:shorts/|watch\?v=|youtu\.be/|\"video_id\"\s*:\s*\")([\w-]{11})")
ORARI = {  # fasce di massimo traffico serale/pausa pranzo per ogni pubblico
    "en": {"tz": "America/New_York", "ore": ["12:15", "17:30", "20:30"]},
    "it": {"tz": "Europe/Rome", "ore": ["13:15", "18:30", "21:15"]},
    "es": {"tz": "America/Mexico_City", "ore": ["13:30", "19:00", "21:30"]},
    "hi": {"tz": "Asia/Kolkata", "ore": ["13:00", "19:30", "21:45"]},
    "pcm": {"tz": "Africa/Lagos", "ore": ["13:00", "19:00", "21:00"]},
}


def tg(token, metodo, **dati):
    j = requests.post(TG.format(t=token, m=metodo), json=dati, timeout=60).json()
    if not j.get("ok"):
        raise RuntimeError(f"Telegram {metodo}: {j.get('description')}")
    return j["result"]


def leggi_didascalia(cap):
    """titolo / descrizione / hashtag / riga '🔥 ... · LINGUA · Credit: canale'."""
    righe = [r for r in cap.split("\n") if r.strip() and not URL_RE.fullmatch(r.strip())]
    tags = " ".join(r for r in righe[1:] if r.startswith("#"))
    fuoco = next((r for r in righe if r.startswith("🔥")), "")
    pezzi = [x.strip() for x in fuoco.split("·")]
    lingua = next((x.lower() for x in pezzi if x.lower() in ORARI), "en")
    canale = fuoco.split("Credit:")[-1].strip() if "Credit:" in fuoco else ""
    desc = " ".join(r for r in righe[1:] if not r.startswith(("#", "🔥")))
    return righe[0], desc, tags, canale, lingua


def prossimo_slot(lingua, occupati, cfg):
    o = (cfg.get("orari") or ORARI).get(lingua) or ORARI["en"]
    tz = ZoneInfo(o["tz"])
    ora = dt.datetime.now(tz)
    for d in range(60):
        g = (ora + dt.timedelta(days=d)).date()
        for hm in o["ore"]:
            h, m = map(int, hm.split(":"))
            t = dt.datetime(g.year, g.month, g.day, h, m, tzinfo=tz)
            k = f"{lingua}|{t.astimezone(dt.timezone.utc).isoformat()}"
            if t > ora + dt.timedelta(minutes=10) and k not in occupati:
                return t, k
    raise RuntimeError("nessun orario libero nei prossimi 60 giorni")


def pubblica(percorso, titolo, desc, tags, canale, lingua, cfg):
    """Upload-Post: un profilo per lingua (config pubblica.profili), altrimenti UPLOAD_POST_USER."""
    chiave = os.environ.get("UPLOAD_POST_API_KEY")
    utente = (cfg.get("profili") or {}).get(lingua) or os.environ.get("UPLOAD_POST_USER")
    if not (chiave and utente):
        raise RuntimeError("mancano i secret UPLOAD_POST_API_KEY / UPLOAD_POST_USER")
    dati = [("user", utente), ("title", f"{titolo} {tags}"[:100]),
            ("description", f"{titolo}\n\n{desc}\n\n{tags}" + (f"\n\nCredit: {canale}" if canale else ""))]
    dati += [("platform[]", p) for p in cfg.get("piattaforme", ["tiktok", "instagram", "youtube"])]
    with open(percorso, "rb") as f:
        r = requests.post("https://api.upload-post.com/api/upload", headers={"Authorization": "Apikey " + chiave},
                          data=dati, files={"video": f}, timeout=900)
    if r.status_code >= 300:
        raise RuntimeError(f"Upload-Post HTTP {r.status_code}: {r.text[:300]}")
    return r.text


def scarica_da_tg(token, file_id):
    path = tg(token, "getFile", file_id=file_id)["file_path"]
    dest = tempfile.mktemp(suffix=".mp4")
    with requests.get(f"https://api.telegram.org/file/bot{token}/{path}", stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for b in r.iter_content(1 << 20):
                f.write(b)
    return dest


def segna(token, chat, msg_id, testo):
    try:
        tg(token, "editMessageReplyMarkup", chat_id=chat, message_id=msg_id,
           reply_markup={"inline_keyboard": [[{"text": testo, "callback_data": "fatto"}]]})
    except Exception as e:
        print("   segna:", e)


def visualizzazioni_yt(ids):
    chiave = os.environ.get("YOUTUBE_API_KEY")
    if not (chiave and ids):
        return None
    tot = 0
    for i in range(0, len(ids), 50):
        r = requests.get("https://www.googleapis.com/youtube/v3/videos", timeout=60,
                         params={"part": "statistics", "id": ",".join(ids[i:i + 50]), "key": chiave}).json()
        tot += sum(int(v["statistics"].get("viewCount", 0)) for v in r.get("items", []))
    return tot


def report(token, st, chat):
    oggi = dt.date.today().isoformat()
    log = st.get("log", [])
    di_oggi = [x for x in log if x["data"].startswith(oggi)]
    per_lingua = {}
    for x in di_oggi:
        per_lingua[x["lingua"]] = per_lingua.get(x["lingua"], 0) + (x["esito"] == "ok")
    errori = sum(x["esito"] != "ok" for x in di_oggi)
    yt_ids = [i for x in log for i in x.get("yt", [])]
    viste = visualizzazioni_yt(yt_ids)
    prossimi = sorted(st["programmati"], key=lambda p: p["quando"])[:5]
    testo = [f"📊 REPORT {oggi}",
             f"Pubblicati oggi: {sum(per_lingua.values())} " + " ".join(f"{k.upper()}:{v}" for k, v in per_lingua.items()),
             f"Errori oggi: {errori}", f"In programma: {len(st['programmati'])}",
             f"Totale pubblicati: {sum(x['esito'] == 'ok' for x in log)}"]
    if viste is not None:
        testo.append(f"Visualizzazioni YouTube totali: {viste:,}".replace(",", "."))
    if prossimi:
        testo.append("Prossimi: " + ", ".join(f"{p['lingua'].upper()} {p['quando'][5:16]} UTC" for p in prossimi))
    tg(token, "sendMessage", chat_id=chat, text="\n".join(testo))


def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    cfg = carica(CONFIG, {}).get("pubblica", {})
    st = carica(STATO, {})
    for k, v in {"ultimo_update": 0, "coda_link": [], "pubblicati": [], "programmati": [], "log": []}.items():
        st.setdefault(k, v)
    chat = carica(os.path.join(RADICE, "archivio.json"), {}).get("chat_id")
    upd = requests.get(TG.format(t=token, m="getUpdates"),
                       params={"offset": st["ultimo_update"] + 1, "timeout": 0}, timeout=60).json().get("result", [])
    for u in upd:
        st["ultimo_update"] = u["update_id"]
        if u.get("message"):
            nuovi = URL_RE.findall(u["message"].get("text") or "")
            if nuovi:
                st["coda_link"] = list(dict.fromkeys(st["coda_link"] + nuovi))[-50:]
                tg(token, "sendMessage", chat_id=u["message"]["chat"]["id"],
                   text=f"📥 {len(nuovi)} link in coda per il clipper (parte entro 3 ore).")
            continue
        q = u.get("callback_query")
        if not q or q.get("data") not in ("ok", "no"):
            continue
        msg = q["message"]
        chiave = f"{msg['chat']['id']}:{msg['message_id']}"
        tg(token, "answerCallbackQuery", callback_query_id=q["id"], text="Ricevuto")
        if q["data"] == "no":
            segna(token, msg["chat"]["id"], msg["message_id"], "❌ Scartata")
            continue
        if chiave in st["pubblicati"] or any(p["msg"] == chiave for p in st["programmati"]):
            continue
        lingua = leggi_didascalia(msg.get("caption", ""))[4]
        occupati = {p["slot"] for p in st["programmati"]} | set(st.get("slot_usati", []))
        quando, slot = prossimo_slot(lingua, occupati, cfg)
        st["programmati"].append({"msg": chiave, "file_id": msg["video"]["file_id"], "caption": msg.get("caption", ""),
                                  "lingua": lingua, "slot": slot, "quando": quando.astimezone(dt.timezone.utc).isoformat()})
        segna(token, msg["chat"]["id"], msg["message_id"], f"🕒 {lingua.upper()} {quando:%d/%m %H:%M} (ora locale)")

    adesso = dt.datetime.now(dt.timezone.utc)
    for p in [p for p in st["programmati"] if dt.datetime.fromisoformat(p["quando"]) <= adesso]:
        voce = {"data": adesso.isoformat(), "lingua": p["lingua"], "esito": "ok", "yt": []}
        chat_id, msg_id = p["msg"].split(":")
        try:
            video = scarica_da_tg(token, p["file_id"])
            risposta = pubblica(video, *leggi_didascalia(p["caption"]), cfg)
            voce["yt"] = list(dict.fromkeys(YT_RE.findall(risposta)))
            st["pubblicati"].append(p["msg"])
            segna(token, chat_id, msg_id, f"✅ Pubblicata {p['lingua'].upper()}")
        except Exception as e:
            voce["esito"] = str(e)[:200]
            segna(token, chat_id, msg_id, "⚠️ Errore: " + str(e)[:40])
            if chat:
                tg(token, "sendMessage", chat_id=chat, text=f"⚠️ Pubblicazione fallita ({p['lingua']}): {str(e)[:300]}")
        st["programmati"].remove(p)
        st.setdefault("slot_usati", []).append(p["slot"])
        st["log"].append(voce)

    if chat and adesso.hour >= 20 and st.get("ultimo_report") != adesso.date().isoformat():
        report(token, st, chat)
        st["ultimo_report"] = adesso.date().isoformat()
    st["pubblicati"], st["log"] = st["pubblicati"][-1000:], st["log"][-2000:]
    st["slot_usati"] = st.get("slot_usati", [])[-500:]
    salva(STATO, st)


if __name__ == "__main__":
    main()
