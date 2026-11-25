# ==== AGENT SCOUT: trova clip reali con licenza libera (Pexels, NASA) ====
import json, os, shutil, urllib.parse, urllib.request

UA = {"User-Agent": "planet-off-scale-regista"}
SOSPETTI = ("©", "copyright", "courtesy of", "used with permission", "all rights reserved")


def _get_json(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        dettaglio = e.read().decode("utf-8", "ignore")[:150].replace("\n", " ")
        raise RuntimeError(f"HTTP {e.code}: {dettaglio}")


def scarica(url, dest, max_mb=200):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as r:
        size = int(r.headers.get("Content-Length") or 0)
        if size and size > max_mb * 1024 * 1024:
            raise RuntimeError(f"file troppo grande ({size // 1048576} MB)")
        with open(dest, "wb") as f:
            shutil.copyfileobj(r, f)


def pexels(query, usati, chiave):
    """Cerca video verticali su Pexels. Licenza Pexels: uso gratuito, attribuzione gradita."""
    if not chiave:
        return None
    url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
        {"query": query, "orientation": "portrait", "size": "medium", "per_page": 15})
    dati = _get_json(url, {"Authorization": chiave})
    for v in dati.get("videos", []):
        vid = "pexels:" + str(v["id"])
        if vid in usati or v.get("duration", 0) < 4:
            continue
        files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4"
                 and f.get("width") and f.get("height") and f["height"] >= f["width"]]
        if not files:
            continue
        # il piu' vicino a 1080 di larghezza, senza esagerare col peso
        files.sort(key=lambda f: abs(f["width"] - 1080))
        autore = (v.get("user") or {}).get("name", "Pexels")
        return {"id": vid, "src": files[0]["link"], "credito": "Pexels",
                "fonte": f"Video by {autore} on Pexels: {v.get('url', '')}"}
    return None


def pixabay(query, usati, chiave):
    """Pixabay video: Content License, uso gratuito anche commerciale, attribuzione gradita."""
    if not chiave:
        return None
    url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode(
        {"key": chiave, "q": query[:100], "per_page": 20, "safesearch": "true"})
    for v in _get_json(url).get("hits", []):
        vid = "pixabay:" + str(v["id"])
        if vid in usati or v.get("duration", 0) < 4:
            continue
        versioni = [x for x in (v.get("videos") or {}).values() if x.get("url")]
        if not versioni:
            continue
        versioni.sort(key=lambda x: abs((x.get("height") or 0) - 1080))
        return {"id": vid, "src": versioni[0]["url"], "credito": "Pixabay",
                "fonte": f"Video by {v.get('user', 'Pixabay')} on Pixabay: {v.get('pageURL', '')}"}
    return None


def nasa(query, usati):
    """NASA Image and Video Library: in genere pubblico dominio; scarta materiale di terzi."""
    url = "https://images-api.nasa.gov/search?" + urllib.parse.urlencode(
        {"q": query, "media_type": "video"})
    items = _get_json(url).get("collection", {}).get("items", [])
    for it in items[:25]:
        d = it["data"][0]
        nid = "nasa:" + d["nasa_id"]
        testo = " ".join(str(d.get(k, "")) for k in
                         ("title", "description", "secondary_creator", "photographer")).lower()
        if nid in usati or any(p in testo for p in SOSPETTI):
            continue
        try:
            assets = _get_json(it["href"])
        except Exception:
            continue
        mp4 = [a for a in assets if isinstance(a, str) and a.lower().endswith(".mp4")]
        for pref in ("~medium.mp4", "~small.mp4", "~mobile.mp4"):
            ok = [a for a in mp4 if a.lower().endswith(pref)]
            if ok:
                return {"id": nid, "src": ok[0].replace("http://", "https://"), "credito": "NASA",
                        "fonte": f"NASA, {d.get('title', '')}: https://images.nasa.gov/details/"
                                 + urllib.parse.quote(d["nasa_id"])}
    return None


VOD_GTA = []


def gameplay_twitch(usati, cartella, n):
    """Riserva: 8 s presi a caso dalle live GTA 6 degli streamer in config (Twitch non blocca i server)."""
    import random, sorgenti
    global VOD_GTA
    if not VOD_GTA:
        cfg = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")))
        c = cfg.get("clipper", {})
        VOD_GTA = [u for u in sorgenti.da_canali([x for x in c.get("canali", []) if "twitch" in x],
                                                  c.get("parole_chiave", ["gta"]), [], quanti=3)]
    for _ in range(6):
        url = random.choice(VOD_GTA)
        dur = sorgenti.info(url)["durata"] or 3600
        t = random.randint(300, max(301, int(dur) - 300))
        vid = f"tw:{url.rsplit('/', 1)[-1]}:{t // 60}"
        if vid in usati:
            continue
        dest = os.path.join(cartella, f"clip{n}.mp4")
        sorgenti.scarica_pezzo(url, t, t + 8, dest)
        canale = sorgenti.info(url)["canale"]
        return dest, {"id": vid, "credito": canale, "fonte": f"{canale} (Twitch): {url}"}
    raise RuntimeError("nessun pezzo Twitch libero")


def gameplay(query, usati, cartella, n):
    """Spezzone di 8 s di gameplay GTA 6: prima YouTube (ricerca), se bloccato le live Twitch."""
    import sorgenti
    try:
        righe = sorgenti._yt(["--flat-playlist", "--yes-playlist", "--print", "%(id)s\t%(duration)s\t%(channel)s",
                              f"ytsearch8:GTA 6 {query} gameplay"]).splitlines()
        for r in righe:
            vid, dur, canale = (r.split("\t") + ["", ""])[:3]
            try:
                dur = float(dur)
            except ValueError:
                continue
            if "yt:" + vid in usati or not 40 < dur < 4 * 3600:
                continue
            url = "https://www.youtube.com/watch?v=" + vid
            dest = os.path.join(cartella, f"clip{n}.mp4")
            inizio = dur * 0.35
            sorgenti.scarica_pezzo(url, inizio, inizio + 8, dest)
            return dest, {"id": "yt:" + vid, "credito": canale or "YouTube", "fonte": f"{canale}: {url}"}
    except Exception as e:
        print(f"   YouTube non disponibile ({str(e)[:120]}), uso Twitch")
    return gameplay_twitch(usati, cartella, n)


def varianti(query, riserva=None):
    """La query originale, poi versioni piu' semplici, poi una ricerca generica di riserva."""
    parole = [p for p in query.replace("'", "").split() if len(p) > 2]
    out = [query]
    if len(parole) > 2:
        out.append(" ".join(parole[-2:]))
    if len(parole) > 1:
        out.append(parole[-1])
    if riserva:
        out.append(riserva)
    return list(dict.fromkeys(q for q in out if q))


def trova_clip(query, fonte_preferita, usati, chiavi, cartella, n, riserva=None):
    """Prova la query e le sue varianti piu' semplici su tutte le fonti."""
    for q in varianti(query, riserva):
        try:
            return _trova_clip(q, fonte_preferita, usati, chiavi, cartella, n)
        except RuntimeError as e:
            print(f"   nessuna clip per '{q}' ({str(e)[:150]}), provo una ricerca piu' semplice")
    raise RuntimeError(f"Nessuna clip trovata per '{query}' (anche con ricerche semplificate)")


def _trova_clip(query, fonte_preferita, usati, chiavi, cartella, n):
    """'gameplay' = YouTube (GTA 6); 'nasa' = spazio; altrimenti stock (Pexels/Pixabay)."""
    if fonte_preferita == "gameplay":
        return gameplay(query, usati, cartella, n)
    stock = ["pexels", "pixabay"]
    ordine = ["nasa"] + stock if fonte_preferita == "nasa" else stock + ["nasa"]
    for f in ordine:
        try:
            if f == "nasa":
                info = nasa(query, usati)
            elif f == "pexels":
                info = pexels(query, usati, chiavi.get("pexels"))
            else:
                info = pixabay(query, usati, chiavi.get("pixabay"))
        except Exception as e:
            print(f"   {f}: errore ricerca ({e})")
            continue
        if not info:
            continue
        dest = os.path.join(cartella, f"clip{n}.mp4")
        try:
            scarica(info["src"], dest)
            return dest, info
        except Exception as e:
            print(f"   {f}: download fallito ({e})")
            usati.add(info["id"])
    raise RuntimeError(f"Nessuna clip trovata per '{query}'")
