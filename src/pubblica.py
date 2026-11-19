# ==== AGENT PUBBLICATORE: legge Telegram (link + pulsanti ✅/❌) e pubblica sui social ====
# Gira ogni 15 minuti. Unico lettore di getUpdates: i link finiscono in pubblica.json -> coda_link.
import os, re, sys, tempfile
import requests

sys.path.insert(0, os.path.dirname(__file__))
from regista import CONFIG, RADICE, carica, salva

STATO = os.path.join(RADICE, "pubblica.json")
TG = "https://api.telegram.org/bot{t}/{m}"
URL_RE = re.compile(r"https?://\S+")


def tg(token, metodo, **dati):
    j = requests.post(TG.format(t=token, m=metodo), json=dati, timeout=60).json()
    if not j.get("ok"):
        raise RuntimeError(f"Telegram {metodo}: {j.get('description')}")
    return j["result"]


def leggi_didascalia(cap):
    """Didascalia scritta dal clipper: titolo / descrizione / hashtag / riga 🔥 (privata)."""
    righe = [r for r in cap.split("\n") if r.strip()]
    titolo = righe[0]
    tags = " ".join(r for r in righe[1:] if r.startswith("#"))
    credito = next((r for r in righe if r.startswith("🔥")), "")
    canale = credito.split("Credit:")[-1].split("·")[0].strip() if "Credit:" in credito else ""
    desc = " ".join(r for r in righe[1:] if not r.startswith(("#", "🔥")))
    return titolo, desc, tags, canale


def pubblica(percorso, titolo, desc, tags, canale, cfg):
    """Upload-Post: un'unica chiave per TikTok, Instagram, YouTube."""
    chiave, utente = os.environ.get("UPLOAD_POST_API_KEY"), os.environ.get("UPLOAD_POST_USER")
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
    return r.json()


def scarica_da_tg(token, file_id):
    path = tg(token, "getFile", file_id=file_id)["file_path"]
    dest = tempfile.mktemp(suffix=".mp4")
    with requests.get(f"https://api.telegram.org/file/bot{token}/{path}", stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for b in r.iter_content(1 << 20):
                f.write(b)
    return dest


def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    cfg = carica(CONFIG, {}).get("pubblica", {})
    st = carica(STATO, {"ultimo_update": 0, "coda_link": [], "pubblicati": []})
    upd = requests.get(TG.format(t=token, m="getUpdates"),
                       params={"offset": st["ultimo_update"] + 1, "timeout": 0}, timeout=60).json().get("result", [])
    for u in upd:
        st["ultimo_update"] = u["update_id"]
        if u.get("message"):
            nuovi = URL_RE.findall(u["message"].get("text") or "")
            st["coda_link"] = list(dict.fromkeys(st["coda_link"] + nuovi))[-50:]
            if nuovi:
                tg(token, "sendMessage", chat_id=u["message"]["chat"]["id"],
                   text=f"📥 In coda per il clipper: {len(nuovi)} link (parte entro 3 ore).")
            continue
        q = u.get("callback_query")
        if not q:
            continue
        msg, scelta = q["message"], q.get("data")
        chiave_msg = f"{msg['chat']['id']}:{msg['message_id']}"
        tg(token, "answerCallbackQuery", callback_query_id=q["id"], text="Ricevuto")
        esito = "❌ Scartata"
        if scelta == "ok" and chiave_msg not in st["pubblicati"]:
            try:
                video = scarica_da_tg(token, msg["video"]["file_id"])
                pubblica(video, *leggi_didascalia(msg.get("caption", "")), cfg)
                st["pubblicati"].append(chiave_msg)
                esito = "✅ Pubblicata"
            except Exception as e:
                esito = f"⚠️ Errore pubblicazione: {str(e)[:150]}"
        tg(token, "editMessageReplyMarkup", chat_id=msg["chat"]["id"], message_id=msg["message_id"],
           reply_markup={"inline_keyboard": [[{"text": esito, "callback_data": "fatto"}]]})
    st["pubblicati"] = st["pubblicati"][-500:]
    salva(STATO, st)


if __name__ == "__main__":
    main()
