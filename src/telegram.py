# ==== INVIO SU TELEGRAM: il video arriva sul telefono di Andrea per l'approvazione ====
import json, urllib.request
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


def messaggio(token, chat_id, testo):
    for i in range(0, len(testo), 3900):  # limite Telegram 4096 caratteri
        _chiama(token, "sendMessage", chat_id=chat_id, text=testo[i:i + 3900],
                disable_web_page_preview="true")


def video(token, chat_id, percorso, didascalia, bottoni=None):
    with open(percorso, "rb") as f:
        r = requests.post(API.format(token=token, metodo="sendVideo"),
                          data={"chat_id": chat_id, "caption": didascalia[:1000],
                                "supports_streaming": "true", "width": 1080, "height": 1920,
                                **({"reply_markup": json.dumps({"inline_keyboard": bottoni})} if bottoni else {})},
                          files={"video": f}, timeout=300)
    j = r.json()
    if not j.get("ok"):
        raise RuntimeError(f"Telegram sendVideo: {j.get('description')}")
