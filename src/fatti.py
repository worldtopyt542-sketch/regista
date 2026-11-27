# ==== FORMAT "OFF SCALE FACTS": 5 fatti fuori scala, voce narrante, filmati NASA (pubblico dominio) / Pixabay ====
# Sceneggiatore (Gemini) -> Scout (NASA, Pixabay, Pexels) -> Voce (Edge TTS) -> Editor -> Critic -> Telegram (gruppo)
# Non dipende da YouTube: e' il format piu' autonomo (nessun video di terzi da verificare).
import datetime, os, random, shutil, sys, traceback

sys.path.insert(0, os.path.dirname(__file__))
import comune, editor, fonti, scrittore, telegram, tendenze
from comune import ARCHIVIO, CONFIG, RADICE, carica, didascalia, lingue, salva


def segmenti(s):
    def f(x):  # vecchi valori "pexels"/"gameplay" -> stock
        return "nasa" if x == "nasa" else "stock"
    out = [{"label": "", "testo": s["hook"], "query": s["hook_query"], "fonte": f(s.get("hook_fonte"))}]
    out += [{"label": it.get("label", ""), "testo": it["testo"], "query": it["query"],
             "fonte": f(it.get("fonte"))} for it in s["items"]]
    out.append({"label": "", "testo": s["finale"], "query": s.get("finale_query") or s["hook_query"],
                "fonte": f(s.get("finale_fonte") or s.get("hook_fonte"))})
    return out


def produci(s, cfg, usati, chiavi, cartella, nome):
    """Clip trovate una volta, poi voce + montaggio per ogni lingua. Ritorna ({cod: (testi, video, ok)}, crediti)."""
    os.makedirs(cartella, exist_ok=True)
    editor.WORK = cartella
    segs, clip, crediti = segmenti(s), [], []
    for n, seg in enumerate(segs):
        print(f"  [{n + 1}/{len(segs)}] {seg['label'] or 'gancio/finale'}: {seg['query']}")
        c, info = fonti.trova_clip(seg["query"], seg["fonte"], usati, chiavi, cartella, n, riserva=s.get("hook_query"))
        usati.add(info["id"])
        clip.append(c)
        crediti.append(info)
    base = {"titolo": s["titolo"], "descrizione": s.get("descrizione", ""), "hashtags": s.get("hashtags") or [],
            "frasi": [seg["testo"] for seg in segs]}
    L = lingue(cfg)
    trad = scrittore.traduci(chiavi["gemini"], base, {k: v["nome"] for k, v in L.items() if k != "en"})
    trad["en"] = base
    out = {}
    for cod, lg in L.items():
        t, pezzi = trad[cod], []
        print(f"  Lingua {cod}")
        for n, (seg, c, info) in enumerate(zip(segs, clip, crediti)):
            mp3 = os.path.join(cartella, f"voce{n}.mp3")
            parole = editor.voce_ai(t["frasi"][n], lg["voce"], mp3)
            pz = os.path.join(cartella, f"seg{n}.mp4")
            editor.monta_segmento(c, mp3, parole, t["frasi"][n], seg["label"], "Footage: " + info["credito"],
                                  pz, n, hook=t["titolo"] if n == 0 else "", font=lg.get("font"),
                                  cta=comune.cta(cod, cfg) if n == len(segs) - 1 else "")
            pezzi.append(pz)
        video = os.path.join(RADICE, "output", nome.replace(".mp4", f"_{cod}.mp4"))
        os.makedirs(os.path.dirname(video), exist_ok=True)
        editor.unisci(pezzi, video)
        editor.marchia(video, video + ".m.mp4"); os.replace(video + ".m.mp4", video)
        out[cod] = (t, video, editor.critic(video, max_sec=cfg.get("durata_max", 45)))
    return out, crediti


def crediti_testo(crediti):
    righe = ["🎥 Footage:"] + [f"- {f}" for f in dict.fromkeys(c["fonte"] for c in crediti)]
    if any(c["credito"] == "NASA" for c in crediti):
        righe.append("NASA footage is public domain. NASA does not endorse this channel.")
    return "\n".join(righe)


def main():
    cfg = carica(CONFIG, {})
    fcfg = cfg.get("fatti", {})
    arch = carica(ARCHIVIO, {"chat_id": None, "titoli": [], "clip_usate": [], "temi_recenti": [], "storico": []})
    chiavi = {"gemini": os.environ.get("GEMINI_API_KEY"), "pexels": os.environ.get("PEXELS_API_KEY"),
              "pixabay": os.environ.get("PIXABAY_API_KEY"), "telegram": os.environ.get("TELEGRAM_BOT_TOKEN"),
              "youtube": os.environ.get("YOUTUBE_API_KEY")}
    mancanti = [k for k in ("gemini", "telegram") if not chiavi[k]]
    if mancanti:
        sys.exit(f"Mancano i secret: {mancanti}. Aggiungili in Settings > Secrets and variables > Actions.")
    if not (chiavi["pexels"] or chiavi["pixabay"]):
        print("Attenzione: nessuna chiave Pixabay/Pexels, uso solo NASA.")
    chat_id = arch.get("chat_id") or telegram.trova_chat_id(chiavi["telegram"])
    if not chat_id:
        sys.exit("Non trovo la chat Telegram: apri il bot sul telefono, premi Avvia e riesegui.")
    arch["chat_id"] = chat_id
    comune.pulisci_gruppi()
    brand = comune.brand(cfg)

    quanti = int(os.environ.get("QUANTI") or fcfg.get("al_giorno", 1))
    temi_tutti = fcfg.get("temi") or ["the scale of the universe"]
    temi = [t for t in temi_tutti if t not in arch["temi_recenti"][-len(temi_tutti) // 2:]] or temi_tutti
    random.shuffle(temi)
    spunti = {}
    if chiavi["youtube"] and fcfg.get("trend_scout", True):
        print("Trend Scout: cerco i temi piu' caldi delle ultime 48 ore...")
        classifica = tendenze.classifica(chiavi["youtube"], temi)
        temi = [c["tema"] for c in classifica]
        spunti = {c["tema"]: c["spunti"] for c in classifica}
    usati = set(arch["clip_usate"])
    oggi = datetime.date.today().isoformat()
    fatti = 0
    soglia_auto = fcfg.get("auto_se_critic_ok", False)

    for i in range(quanti):
        tema = temi[i % len(temi)]
        print(f"\n=== Facts {i + 1}/{quanti} - tema: {tema}")
        cartella = os.path.join(RADICE, "lavoro", str(i))
        try:
            s = scrittore.scrivi(chiavi["gemini"], tema, arch["titoli"], cfg.get("modello_gemini", "auto"),
                                 spunti=spunti.get(tema), brand=brand)
            print("  Titolo:", s["titolo"])
            versioni, crediti = produci(s, cfg, usati, chiavi, cartella, f"{oggi}_facts{i + 1}.mp4")
            credito = ", ".join(dict.fromkeys(c["credito"] for c in crediti))[:200]
            tutti_ok = all(v[2] for v in versioni.values())
            gruppo = {"id": comune.nuovo_gruppo(), "creato": datetime.datetime.utcnow().isoformat(), "formato": "facts",
                      "titolo": s["titolo"], "punteggio": 0, "critic_ok": tutti_ok, "auto": bool(soglia_auto and tutti_ok),
                      "fonte": None, "crediti": crediti_testo(crediti),
                      "verifica": [it.get("verifica", "") for it in s["items"]],
                      "versioni": {cod: {"titolo": t["titolo"], "descrizione": t.get("descrizione", ""),
                                         "hashtags": comune.hashtag(t, cfg)} for cod, (t, _, _) in versioni.items()}}
            controlli = "\n".join(f"{it.get('label')}: {it.get('verifica', '-')}" for it in s["items"])
            telegram.invia_gruppo(chiavi["telegram"], chat_id, gruppo,
                                  {cod: (v, didascalia(t, cod, credito, "FACTS" + ("" if ok else " · critic ⚠️")))
                                   for cod, (t, v, ok) in versioni.items()},
                                  "🔎 Fonti da controllare prima di approvare:\n" + controlli)
            comune.salva_gruppo(gruppo)
            arch["titoli"] = (arch["titoli"] + [s["titolo"]])[-300:]
            arch["temi_recenti"] = (arch["temi_recenti"] + [tema])[-50:]
            arch["clip_usate"] = sorted(usati)[-3000:]
            arch["storico"] = (arch["storico"] + [{"data": oggi, "titolo": s["titolo"], "tema": tema,
                                                   "critic_ok": tutti_ok, "clip": [c["id"] for c in crediti]}])[-300:]
            fatti += 1
        except Exception as e:
            traceback.print_exc()
            try:
                telegram.messaggio(chiavi["telegram"], chat_id, f"❌ Facts {i + 1} non riuscito ({tema}): {e}")
            except Exception:
                pass
        finally:
            shutil.rmtree(cartella, ignore_errors=True)
        salva(ARCHIVIO, arch)
    if fatti == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
