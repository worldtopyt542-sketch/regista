# ==== AGENT SCOUT: trova clip reali con licenza libera (NASA pubblico dominio, Pixabay, Pexels) ====
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
        # dalla qualita' migliore alla piu' leggera (large = 1080p, orig = master, medium = 720p): se una e'
        # troppo pesante si prova la successiva; ~small/~mobile (360p) solo come ultima riserva
        alt = [a.replace("http://", "https://") for pref in ("~large.mp4", "~orig.mp4", "~medium.mp4", "~small.mp4")
               for a in mp4 if a.lower().endswith(pref)]
        if alt:
            return {"id": nid, "src": alt[0], "alt": alt, "credito": "NASA",
                    "fonte": f"NASA, {d.get('title', '')}: https://images.nasa.gov/details/"
                             + urllib.parse.quote(d["nasa_id"])}
    return None


NO_FOTO = ("infographic", "chart", "diagram", "graph", "logo", "portrait", "conference", "briefing", "poster",
           "patch", "insignia", "headshot", "award", "ceremony", "meeting", "illustration of text")


def nasa_foto(query, usati):
    """Foto NASA ad alta risoluzione (Hubble, Webb, sonde): pubblico dominio. Diventano clip con zoom lento."""
    url = "https://images-api.nasa.gov/search?" + urllib.parse.urlencode({"q": query, "media_type": "image"})
    items = _get_json(url).get("collection", {}).get("items", [])
    for it in items[:30]:
        d = it["data"][0]
        nid = "nasafoto:" + d["nasa_id"]
        testo = " ".join(str(d.get(k, "")) for k in
                         ("title", "description", "secondary_creator", "photographer", "keywords")).lower()
        if nid in usati or any(p in testo for p in SOSPETTI + NO_FOTO):
            continue
        try:
            assets = _get_json(it["href"])
        except Exception:
            continue
        jpg = [a for a in assets if isinstance(a, str) and a.lower().endswith((".jpg", ".jpeg", ".png", ".tif"))]
        alt = [a.replace("http://", "https://") for pref in ("~large.jpg", "~orig.jpg", "~orig.png", "~medium.jpg")
               for a in jpg if a.lower().endswith(pref)]
        if alt:
            return {"id": nid, "src": alt[0], "alt": alt, "credito": "NASA", "foto": True,
                    "fonte": f"NASA, {d.get('title', '')}: https://images.nasa.gov/details/"
                             + urllib.parse.quote(d["nasa_id"])}
    return None


def foto_in_clip(img, dest, secondi=10, minimo=1000):
    """Foto -> clip alta 1920 (o larga 1080) senza tagliarla: il taglio 9:16 lo fa il montaggio intorno al
    soggetto, e anche lo zoom lento. Scarta le foto troppo piccole."""
    import editor
    dim = editor.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                      "-of", "csv=p=0:s=x", img]).strip().split("x")
    if len(dim) != 2 or max(int(dim[0]), int(dim[1])) < minimo:
        return False
    editor.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", img, "-t", str(secondi), "-r", "30",
                "-vf", "scale='if(gt(a,9/16),-2,1080)':'if(gt(a,9/16),1920,-2)',crop='trunc(iw/2)*2':'trunc(ih/2)*2',"
                "format=yuv420p",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", dest])
    return True


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


RISERVE = ("galaxy", "stars night sky", "earth from space", "nature")


def trova_clip(query, fonte_preferita, usati, chiavi, cartella, n, riserva=None):
    """Prova la query e le sue varianti piu' semplici su tutte le fonti, poi ricerche generiche:
    un segmento senza clip non deve far perdere l'intero video."""
    for q in varianti(query, riserva) + [r for r in RISERVE if r not in (query, riserva)]:
        try:
            return _trova_clip(q, fonte_preferita, usati, chiavi, cartella, n)
        except RuntimeError as e:
            print(f"   nessuna clip per '{q}' ({str(e)[:150]}), provo una ricerca piu' semplice")
    raise RuntimeError(f"Nessuna clip trovata per '{query}' (anche con ricerche semplificate)")


SPENTE = set()  # fonti con chiave rifiutata: non si riprovano per tutta l'esecuzione


CONTROLLO = """These are {n} frames, in time order, from a video clip we may use as background footage in a
cinematic space/nature Short. For EACH frame decide if it is CLEAN: real or rendered imagery (space, planets, stars,
Earth from orbit, rockets, spacecraft, nature, animals) that fills the frame. NOT clean: titles, captions, slides,
credits or any readable text; logos or watermarks; people talking to the camera, interviews, press conferences,
studio or office shots; charts and diagrams; black, white or blank screens; heavy blur.
Also give, for each frame, the horizontal position of the main subject (planet, rocket, animal, astronaut...)
from 0.0 (left edge) to 1.0 (right edge), 0.5 if centred or if there is no single subject: the clip will be cropped
to a vertical 9:16 window around it.
Reply JSON only: {{"pulito": [true, false, ...], "centro_x": [0.5, ...]}} with exactly {n} values each."""


def pulisci_clip(path, chiave, quadri=6):
    """Gemini guarda {quadri} fotogrammi: la clip si accorcia al tratto pulito piu' lungo, o si scarta.
    Ritorna None se va scartata, altrimenti la posizione orizzontale del soggetto (0-1) per il taglio 9:16."""
    import editor, scrittore
    dur = editor.durata(path)
    if dur < 1.5:
        return None
    tempi = [dur * (k + 0.5) / quadri for k in range(quadri)]
    foto = []
    for k, t in enumerate(tempi):
        jpg = path + f".{k}.jpg"
        editor.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1",
                    "-vf", "scale=384:-2", jpg])
        foto.append((f"Frame {k + 1} (t={t:.0f}s)", jpg))
    try:
        risposta = scrittore.gemini(chiave, CONTROLLO.format(n=quadri), 0.1, foto)
        esito, centri = risposta.get("pulito") or [], risposta.get("centro_x") or []
    except Exception as e:
        print(f"   controllo clip non riuscito ({str(e)[:80]}), la uso com'e'")
        return 0.5
    finally:
        for _, jpg in foto:
            try:
                os.remove(jpg)
            except OSError:
                pass
    esito = [bool(x) for x in esito][:quadri] + [False] * (quadri - len(esito))
    migliore, inizio = (0, 0), None  # (lunghezza, primo indice) del tratto pulito piu' lungo
    for k, ok in enumerate(esito + [False]):
        if ok and inizio is None:
            inizio = k
        elif not ok and inizio is not None:
            migliore = max(migliore, (k - inizio, inizio))
            inizio = None
    lung, primo = migliore
    print(f"   controllo clip: {''.join('v' if x else 'x' for x in esito)}")
    if lung < min(2, quadri):
        return None
    validi = []
    for x in centri[primo:primo + lung]:
        try:
            validi.append(min(max(float(x), 0.0), 1.0))
        except (TypeError, ValueError):
            pass
    centro = round(sum(validi) / len(validi), 3) if validi else 0.5
    print(f"   soggetto a {centro:.2f} della larghezza")
    passo = dur / quadri
    a, b = primo * passo, (primo + lung) * passo
    if a > 0.5 or b < dur - 0.5:  # tiene solo il tratto pulito
        tmp = path + ".taglio.mp4"
        editor.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.2f}", "-to", f"{b:.2f}", "-i", path, "-an",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", tmp])
        os.replace(tmp, path)
    return centro


def orizzontale(path):
    import editor
    try:
        w, h = editor.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                           "-of", "csv=p=0:s=x", path]).strip().split("x")[:2]
        return int(w) > int(h)
    except Exception:
        return False


def _trova_clip(query, fonte_preferita, usati, chiavi, cartella, n):
    """'nasa' = spazio (pubblico dominio); altrimenti stock (Pixabay/Pexels: licenze d'uso gratuito).
    Le clip NASA (spesso con titoli, loghi, conferenze stampa) passano dal controllo di Gemini: fino a 4 candidate."""
    stock = ["pexels", "pixabay"]
    ordine = ["nasa", "nasafoto"] + stock if fonte_preferita == "nasa" else stock + ["nasa", "nasafoto"]
    for f in ordine:
        for _ in range(4 if f == "nasa" and chiavi.get("gemini") else 3 if f == "nasafoto" else 1):
            if f in SPENTE:
                break
            try:
                if f == "nasa":
                    info = nasa(query, usati)
                elif f == "nasafoto":
                    info = nasa_foto(query, usati)
                elif f == "pexels":
                    info = pexels(query, usati, chiavi.get("pexels"))
                else:
                    info = pixabay(query, usati, chiavi.get("pixabay"))
            except Exception as e:
                print(f"   {f}: errore ricerca ({e})")
                if "api key" in str(e).lower() or "HTTP 401" in str(e) or "HTTP 403" in str(e):
                    SPENTE.add(f)
                    print(f"   {f}: chiave rifiutata, la salto fino alla fine (controlla il secret)")
                break
            if not info:
                break
            dest = os.path.join(cartella, f"clip{n}.mp4")
            scaricata = None
            for src in info.get("alt") or [info["src"]]:
                try:
                    if info.get("foto"):
                        img = os.path.join(cartella, f"foto{n}" + os.path.splitext(src)[1].lower())
                        scarica(src, img, max_mb=60)
                        if not foto_in_clip(img, dest):
                            raise RuntimeError("foto troppo piccola")
                    else:
                        scarica(src, dest)
                    scaricata = src
                    break
                except Exception as e:
                    print(f"   {f}: download fallito ({e})")
            usati.add(info["id"])
            if not scaricata:
                continue
            centro = 0.5
            if chiavi.get("gemini") and (f == "nasa" or orizzontale(dest)):
                centro = pulisci_clip(dest, chiavi["gemini"], 6 if f == "nasa" else 2 if info.get("foto") else 3)
                if centro is None:
                    print(f"   {f}: clip scartata (testo, loghi o persone che parlano): {info['id']}")
                    continue
            return dest, {**info, "src": scaricata, "centro_x": centro}
    raise RuntimeError(f"Nessuna clip trovata per '{query}'")
