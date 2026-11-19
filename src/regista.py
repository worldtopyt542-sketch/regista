# ==== REGISTA: fa lavorare tutti gli agent ogni mattina ====
# Sceneggiatore (Gemini) -> Scout (Pexels/NASA) -> Voce (Edge TTS) -> Editor -> Critic -> Telegram
import datetime, json, os, random, shutil, sys, traceback

sys.path.insert(0, os.path.dirname(__file__))
import editor, fonti, scrittore, telegram, tendenze

BOTTONI = [[{"text": "✅ Pubblica", "callback_data": "ok"}, {"text": "❌ Scarta", "callback_data": "no"}]]
RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVIO = os.path.join(RADICE, "archivio.json")
CONFIG = os.path.join(RADICE, "config.json")


def carica(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def salva(path, dati):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, indent=1)


def segmenti(s):
    out = [{"label": "", "testo": s["hook"], "query": s["hook_query"], "fonte": s.get("hook_fonte", "pexels")}]
    out += [{"label": it.get("label", ""), "testo": it["testo"], "query": it["query"],
             "fonte": it.get("fonte", "pexels")} for it in s["items"]]
    out.append({"label": "", "testo": s["finale"], "query": s.get("finale_query") or s["hook_query"],
                "fonte": s.get("finale_fonte", s.get("hook_fonte", "pexels"))})
    return out


def lingue(cfg):
    return cfg.get("lingue") or {"en": {"nome": "English", "voce": cfg.get("voce", "en-US-GuyNeural")}}


def didascalia(t, cod, credito, extra=""):
    """Formato letto dal Pubblicatore: titolo / descrizione / hashtag / riga 🔥."""
    return (f"{t['titolo']}\n\n{t.get('descrizione', '')}\n\n{' '.join(t.get('hashtags') or ['#gta6'])}\n\n"
            f"🔥 {extra} · {cod.upper()} · Credit: {credito}")[:1000]


def produci(s, cfg, usati, chiavi, cartella, nome):
    """Clip trovate una volta, poi voce + montaggio per ogni lingua. Ritorna ([(cod, testi, video, ok)], crediti)."""
    os.makedirs(cartella, exist_ok=True)
    editor.WORK = cartella
    segs, clip, crediti = segmenti(s), [], []
    for n, seg in enumerate(segs):
        print(f"  [{n + 1}/7] {seg['label'] or 'gancio/finale'}: {seg['query']}")
        c, info = fonti.trova_clip(seg["query"], seg["fonte"], usati, chiavi, cartella, n, riserva=s.get("hook_query"))
        usati.add(info["id"])
        clip.append(c)
        crediti.append(info)
    base = {"titolo": s["titolo"], "descrizione": s.get("descrizione", ""), "hashtags": s.get("hashtags") or ["#gta6"],
            "frasi": [seg["testo"] for seg in segs]}
    L = lingue(cfg)
    trad = scrittore.traduci(chiavi["gemini"], base, {k: v["nome"] for k, v in L.items() if k != "en"})
    trad["en"] = base
    out = []
    for cod, lg in L.items():
        t, pezzi = trad[cod], []
        print(f"  Lingua {cod}")
        for n, (seg, c, info) in enumerate(zip(segs, clip, crediti)):
            mp3 = os.path.join(cartella, f"voce{n}.mp3")
            parole = editor.voce_ai(t["frasi"][n], lg["voce"], mp3)
            pz = os.path.join(cartella, f"seg{n}.mp4")
            editor.monta_segmento(c, mp3, parole, t["frasi"][n], seg["label"], "Footage: " + info["credito"],
                                  pz, n, hook=t["titolo"] if n == 0 else "", font=lg.get("font"))
            pezzi.append(pz)
        video = os.path.join(RADICE, "output", nome.replace(".mp4", f"_{cod}.mp4"))
        os.makedirs(os.path.dirname(video), exist_ok=True)
        editor.unisci(pezzi, video)
        out.append((cod, t, video, editor.critic(video, max_sec=cfg.get("durata_max", 45))))
    return out, crediti


def descrizione(s, crediti):
    fonti_uniche = list(dict.fromkeys(c["fonte"] for c in crediti))
    righe = [s["titolo"], "", " ".join(s.get("hashtags") or ["#shorts"]), "", "Footage credits:"]
    righe += [f"- {f}" for f in fonti_uniche]
    if any(c["credito"] == "NASA" for c in crediti):
        righe.append("NASA footage is public domain. NASA does not endorse this channel.")
    return "\n".join(righe)


def main():
    cfg = carica(CONFIG, {})
    arch = carica(ARCHIVIO, {"chat_id": None, "titoli": [], "clip_usate": [], "temi_recenti": [], "storico": []})
    chiavi = {"gemini": os.environ.get("GEMINI_API_KEY"), "pexels": os.environ.get("PEXELS_API_KEY"),
              "pixabay": os.environ.get("PIXABAY_API_KEY"),
              "telegram": os.environ.get("TELEGRAM_BOT_TOKEN"),
              "youtube": os.environ.get("YOUTUBE_API_KEY")}
    mancanti = [k for k in ("gemini", "telegram") if not chiavi[k]]
    if mancanti:
        sys.exit(f"Mancano i secret: {mancanti}. Aggiungili in Settings > Secrets and variables > Actions.")
    if not (chiavi["pexels"] or chiavi["pixabay"]):
        print("Attenzione: nessuna chiave Pexels/Pixabay, uso solo NASA.")

    chat_id = arch.get("chat_id") or telegram.trova_chat_id(chiavi["telegram"])
    if not chat_id:
        sys.exit("Non trovo la chat Telegram: apri il bot sul telefono, premi Avvia e riesegui.")
    arch["chat_id"] = chat_id

    quanti = int(os.environ.get("QUANTI") or cfg.get("video_al_giorno", 3))
    temi = [t for t in cfg["temi"] if t not in arch["temi_recenti"][-len(cfg["temi"]) // 2:]] or cfg["temi"]
    random.shuffle(temi)
    spunti = {}
    if chiavi["youtube"]:
        print("Trend Scout: cerco i temi piu' caldi delle ultime 48 ore...")
        classifica = tendenze.classifica(chiavi["youtube"], temi)
        temi = [c["tema"] for c in classifica]
        spunti = {c["tema"]: c["spunti"] for c in classifica}
        arch.setdefault("tendenze", []).append({"data": datetime.date.today().isoformat(),
                                                "classifica": [[c["tema"], c["punteggio"]] for c in classifica]})
        arch["tendenze"] = arch["tendenze"][-30:]
    else:
        print("Trend Scout spento: manca YOUTUBE_API_KEY (temi a rotazione).")
    usati = set(arch["clip_usate"])
    oggi = datetime.date.today().isoformat()
    fatti = 0

    for i in range(quanti):
        tema = temi[i % len(temi)]
        print(f"\n=== Video {i + 1}/{quanti} - tema: {tema}")
        try:
            s = scrittore.scrivi(chiavi["gemini"], tema, arch["titoli"], cfg.get("modello_gemini", "auto"),
                                spunti=spunti.get(tema))
            print("  Titolo:", s["titolo"])
            nome = f"{oggi}_{i + 1}.mp4"
            versioni, crediti = produci(s, cfg, usati, chiavi, os.path.join(RADICE, "lavoro", str(i)), nome)
            credito = ", ".join(dict.fromkeys(c["credito"] for c in crediti))[:200]
            for cod, t, video, ok in versioni:
                telegram.video(chiavi["telegram"], chat_id, video,
                               didascalia(t, cod, credito, "news" if ok else "news · critic ⚠️"), bottoni=BOTTONI)
            controlli = "\n".join(f"{it.get('label')}: {it.get('verifica', '-')}" for it in s["items"])
            telegram.messaggio(chiavi["telegram"], chat_id, f"🔎 Fonti da controllare per «{s['titolo']}»:\n" + controlli)
            ok = all(v[3] for v in versioni)
            arch["titoli"].append(s["titolo"])
            arch["temi_recenti"].append(tema)
            arch["clip_usate"] = sorted(usati)
            arch["storico"].append({"data": oggi, "titolo": s["titolo"], "tema": tema, "critic_ok": ok,
                                    "clip": [c["id"] for c in crediti]})
            fatti += 1
        except Exception as e:
            traceback.print_exc()
            try:
                telegram.messaggio(chiavi["telegram"], chat_id, f"❌ Video {i + 1} non riuscito ({tema}): {e}")
            except Exception:
                pass
        finally:
            shutil.rmtree(os.path.join(RADICE, "lavoro", str(i)), ignore_errors=True)
        salva(ARCHIVIO, arch)

    telegram.messaggio(chiavi["telegram"], chat_id,
                       f"📰 {fatti}/{quanti} video di news GTA 6 pronti qui sopra. Premi ✅ per pubblicarli.")
    if fatti == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
