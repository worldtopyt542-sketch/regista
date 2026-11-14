# ==== AGENT TREND SCOUT: quali temi stanno esplodendo oggi su YouTube ====
# Legge solo titoli e numeri pubblici dei video piu' visti delle ultime ore.
# Non scarica e non riusa nessun video: passa allo Sceneggiatore solo i TEMI caldi.
import datetime, json, math, urllib.parse, urllib.request

API = "https://www.googleapis.com/youtube/v3/"


def _chiama(endpoint, chiave, **params):
    params["key"] = chiave
    url = API + endpoint + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "ignore")
        if "quotaExceeded" in msg:
            raise RuntimeError("quota YouTube giornaliera finita")
        raise RuntimeError(f"YouTube HTTP {e.code}: {msg[:200]}")


def segnali_tema(chiave, tema, ore=48, quanti=10, adesso=None):
    """Ritorna (punteggio, [titoli piu' caldi]) per un tema."""
    adesso = adesso or datetime.datetime.now(datetime.timezone.utc)
    dopo = (adesso - datetime.timedelta(hours=ore)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ris = _chiama("search", chiave, part="id", q=tema, type="video", order="viewCount",
                  publishedAfter=dopo, maxResults=quanti, relevanceLanguage="en")
    ids = [it["id"]["videoId"] for it in ris.get("items", []) if it.get("id", {}).get("videoId")]
    if not ids:
        return 0.0, []
    det = _chiama("videos", chiave, part="snippet,statistics", id=",".join(ids))
    righe = []
    for v in det.get("items", []):
        pub = datetime.datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z", "+00:00"))
        ore_vita = max(1.0, (adesso - pub).total_seconds() / 3600)
        views = int(v.get("statistics", {}).get("viewCount", 0))
        righe.append((views / ore_vita, v["snippet"]["title"]))
    righe.sort(reverse=True)
    top = righe[:3]
    # punteggio: views/ora dei 3 video piu' caldi, in scala logaritmica
    punteggio = round(sum(math.log10(1 + x[0]) for x in top), 2)
    return punteggio, [t for _, t in top]


def classifica(chiave, temi):
    """Ordina i temi dal piu' caldo al piu' freddo. In caso di errore ritorna i temi com'erano."""
    risultati = []
    for tema in temi:
        try:
            p, titoli = segnali_tema(chiave, tema)
        except Exception as e:
            print(f"   Trend Scout: '{tema}' saltato ({e})")
            if "quota" in str(e):
                break
            p, titoli = 0.0, []
        risultati.append({"tema": tema, "punteggio": p, "spunti": titoli})
        print(f"   Trend Scout: {tema} -> {p}")
    visti = {r["tema"] for r in risultati}
    risultati += [{"tema": t, "punteggio": 0.0, "spunti": []} for t in temi if t not in visti]
    risultati.sort(key=lambda r: -r["punteggio"])
    return risultati
