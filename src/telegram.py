# ==== INVIO SU TELEGRAM: i video arrivano al proprietario del bot per l'approvazione ====
import json
import requests

API = "https://api.telegram.org/bot{token}/{metodo}"


def _chiama(token, metodo, **dati):
    r = requests.post(API.format(token=token, metodo=metodo), data=dati, timeout=60)
    j = r.json()
    if not j.get("ok"):
        raise RuntimeError(f"Telegram {metodo}: {j.get('description')}")
    return j["result"]


def trova_chat_id(token):
    """Legge l'ultimo messaggio inviato al bot (serve aver premuto Avvia)."""
    r = requests.get(API.format(token=token, metodo="getUpdates"), timeout=60).json()
    for u in reversed(r.get("result", [])):
        msg = u.get("message") or u.get("my_chat_member") or {}
        chat = msg.get("chat")
        if chat and chat.get("type") == "private":
            return chat["id"]
    return None


def messaggio(token, chat_id, testo, bottoni=None):
    r = None
    for i in range(0, len(testo), 3900):  # limite Telegram 4096 caratteri
        extra = {"reply_markup": json.dumps({"inline_keyboard": bottoni})} if bottoni and i + 3900 >= len(testo) else {}
        r = _chiama(token, "sendMessage", chat_id=chat_id, text=testo[i:i + 3900],
                    disable_web_page_preview="true", **extra)
    return r


def video(token, chat_id, percorso, didascalia, bottoni=None, silenzioso=True, tentativi=3):
    """Ritorna il messaggio inviato (serve il file_id del video per pubblicarlo dopo)."""
    for t in range(tentativi):  # l'upload su Telegram a volte va in timeout: riprova
        try:
            return _video(token, chat_id, percorso, didascalia, bottoni, silenzioso)
        except requests.exceptions.RequestException as e:
            if t == tentativi - 1:
                raise
            print("   Telegram: invio fallito, riprovo", e)


def _video(token, chat_id, percorso, didascalia, bottoni=None, silenzioso=True):
    with open(percorso, "rb") as f:
        r = requests.post(API.format(token=token, metodo="sendVideo"),
                          data={"chat_id": chat_id, "caption": didascalia[:1000],
                                "supports_streaming": "true", "width": 1080, "height": 1920,
                                "disable_notification": "true" if silenzioso else "false",
                                **({"reply_markup": json.dumps({"inline_keyboard": bottoni})} if bottoni else {})},
                          files={"video": f}, timeout=300)
    j = r.json()
    if not j.get("ok"):
        raise RuntimeError(f"Telegram sendVideo: {j.get('description')}")
    return j["result"]


def bottoni_gruppo(gid, lingue):
    etichetta = "✅ Pubblica " + " ".join(l.upper() for l in lingue)
    return [[{"text": etichetta, "callback_data": f"ok:{gid}"}, {"text": "❌ Scarta", "callback_data": f"no:{gid}"}]]


def invia_gruppo(token, chat_id, gruppo, video_per_lingua, extra=""):
    """Manda tutte le versioni (una per lingua) e UN solo messaggio coi bottoni che approva tutto il gruppo.
    video_per_lingua: {cod: (percorso, didascalia)}. Riempie gruppo['versioni'][cod]['file_id'/'msg']."""
    for cod, (percorso, cap) in video_per_lingua.items():
        m = video(token, chat_id, percorso, cap)
        v = gruppo["versioni"][cod]
        v["file_id"], v["msg"] = m["video"]["file_id"], f"{chat_id}:{m['message_id']}"
    stato = "🤖 Auto-approvata: va in programma da sola" if gruppo.get("auto") else "Approva una volta sola per tutte le lingue"
    m = messaggio(token, chat_id, f"🎬 {gruppo['titolo']}\n{extra}\n{stato}",
                  bottoni=None if gruppo.get("auto") else bottoni_gruppo(gruppo["id"], list(video_per_lingua)))
    gruppo["msg_bottoni"] = f"{chat_id}:{m['message_id']}"
    return gruppo
