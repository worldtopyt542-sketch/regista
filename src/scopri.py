# ==== AGENT SCOPRITORE: video virali (>= 1M views) con licenza Creative Commons BY su YouTube ====
# Usa l'API ufficiale (filtro videoLicense=creativeCommon) e ricontrolla la licenza di ogni video.
import random, re
import requests

API = "https://www.googleapis.com/youtube/v3/"


def _get(endpoint, chiave, **p):
    r = requests.get(API + endpoint, params={**p, "key": chiave}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"YouTube API {r.status_code}: {r.text[:200]}")
    return r.json()


def durata_iso(s):
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    d, h, mi, se = (int(x or 0) for x in m.groups()) if m else (0, 0, 0, 0)
    return d * 86400 + h * 3600 + mi * 60 + se


def cerca(chiave, ricerche, fatti, min_views=1_000_000, quanti=4):
    """Ritorna [{url, titolo, canale, views, durata}] di video CC BY virali non ancora usati."""
    trovati = []
    ricerche = list(ricerche)
    random.shuffle(ricerche)
    for q in ricerche:
        for durata in ("medium", "long"):  # 4-20 min e > 20 min: materiale per piu' clip
            try:
                ris = _get("search", chiave, part="id", q=q, type="video", videoLicense="creativeCommon",
                           order="viewCount", videoDuration=durata, maxResults=25,
                           relevanceLanguage="en", regionCode="US")
                ids = [i["id"]["videoId"] for i in ris.get("items", [])]
                if not ids:
                    continue
                det = _get("videos", chiave, part="snippet,statistics,status,contentDetails", id=",".join(ids))
            except RuntimeError as e:
                print("   Scopritore:", e)
                if "quota" in str(e).lower():
                    return trovati
                continue
            for v in det.get("items", []):
                url = "https://www.youtube.com/watch?v=" + v["id"]
                views = int(v.get("statistics", {}).get("viewCount", 0))
                lingua = (v["snippet"].get("defaultAudioLanguage") or v["snippet"].get("defaultLanguage") or "en")[:2]
                if (v.get("status", {}).get("license") != "creativeCommon" or views < min_views or lingua != "en"
                        or re.search(r"[\u0900-\u097F]", v["snippet"]["title"])
                        or url in fatti or any(t["url"] == url for t in trovati)):
                    continue
                trovati.append({"url": url, "titolo": v["snippet"]["title"], "canale": v["snippet"]["channelTitle"],
                                "views": views, "durata": durata_iso(v["contentDetails"].get("duration"))})
        if len(trovati) >= quanti:
            break
    trovati.sort(key=lambda t: -t["views"])
    for t in trovati[:quanti]:
        print(f"   Scopritore: {t['views']:,} views · {t['titolo'][:60]} ({t['canale']})")
    return trovati[:quanti]


class LicenzaNonLibera(RuntimeError):
    """Errore definitivo: il video non si puo' usare (non riprovare)."""


def id_youtube(url):
    m = re.search(r"(?:v=|youtu\.be/|shorts/|live/)([\w-]{11})", url or "")
    return m.group(1) if m else None


DOMINI_PUBBLICO_DOMINIO = ("nasa.gov",)  # NASA: pubblico dominio (salvo materiale di terzi)


def verifica(chiave, url):
    """Ritorna {'autore','titolo','url','licenza'} se il video si puo' usare, altrimenti LicenzaNonLibera.
    Vale anche per i link mandati a mano o via Telegram: niente piu' '(CC BY)' dato per scontato."""
    vid = id_youtube(url)
    if vid:
        if not chiave:  # temporaneo: il video si riprova quando c'e' la chiave
            raise RuntimeError("manca YOUTUBE_API_KEY: non posso verificare la licenza")
        it = _get("videos", chiave, part="snippet,status", id=vid).get("items", [])
        if not it:
            raise LicenzaNonLibera("video YouTube non trovato")
        if it[0].get("status", {}).get("license") != "creativeCommon":
            raise LicenzaNonLibera("licenza YouTube standard (non Creative Commons): non si puo' usare")
        sn = it[0]["snippet"]
        return {"autore": sn.get("channelTitle", ""), "titolo": sn.get("title", ""),
                "url": "https://www.youtube.com/watch?v=" + vid, "licenza": "CC BY"}
    dominio = re.sub(r"^https?://([^/]+).*", r"\1", url or "").lower()
    if any(dominio == d or dominio.endswith("." + d) for d in DOMINI_PUBBLICO_DOMINIO):
        return {"autore": "NASA", "titolo": "", "url": url, "licenza": "Public domain"}
    raise LicenzaNonLibera(f"fonte non ammessa ({dominio}): solo YouTube CC BY o NASA")
