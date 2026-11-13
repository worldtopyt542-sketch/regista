# ==== REGISTA: fa lavorare tutti gli agent ogni mattina ====
# Sceneggiatore (Gemini) -> Scout (Pexels/NASA) -> Voce (Edge TTS) -> Editor -> Critic -> Telegram
import datetime, json, os, random, shutil, sys, traceback

sys.path.insert(0, os.path.dirname(__file__))
import editor, fonti, scrittore, telegram

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


def produci(s, cfg, usati, chiavi, cartella, nome):
    """Ritorna (percorso video, lista fonti, esito critic)."""
    os.makedirs(cartella, exist_ok=True)
    editor.WORK = cartella
    pezzi, crediti = [], []
    for n, seg in enumerate(segmenti(s)):
        print(f"  [{n + 1}/7] {seg['label'] or 'gancio/finale'}: {seg['query']}")
        clip, info = fonti.trova_clip(seg["query"], seg["fonte"], usati, chiavi, cartella, n)
        usati.add(info["id"])
        crediti.append(info)
        mp3 = os.path.join(cartella, f"voce{n}.mp3")
        parole = editor.voce_ai(seg["testo"], cfg["voce"], mp3)
        out = os.path.join(cartella, f"seg{n}.mp4")
        editor.monta_segmento(clip, mp3, parole, seg["testo"], seg["label"], "Footage: " + info["credito"],
                              out, n, hook=s["titolo"] if n == 0 else "")
        pezzi.append(out)
    video = os.path.join(RADICE, "output", nome)
    os.makedirs(os.path.dirname(video), exist_ok=True)
    editor.unisci(pezzi, video)
    ok = editor.critic(video, max_sec=cfg.get("durata_max", 45))
    return video, crediti, ok


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
              "telegram": os.environ.get("TELEGRAM_BOT_TOKEN")}
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
    usati = set(arch["clip_usate"])
    oggi = datetime.date.today().isoformat()
    fatti = 0

    for i in range(quanti):
        tema = temi[i % len(temi)]
        print(f"\n=== Video {i + 1}/{quanti} - tema: {tema}")
        try:
            s = scrittore.scrivi(chiavi["gemini"], tema, arch["titoli"], cfg.get("modello_gemini", "gemini-2.5-flash"))
            print("  Titolo:", s["titolo"])
            nome = f"{oggi}_{i + 1}.mp4"
            video, crediti, ok = produci(s, cfg, usati, chiavi, os.path.join(RADICE, "lavoro", str(i)), nome)
            desc = descrizione(s, crediti)
            controlli = "\n".join(f"{it.get('label')}: {it.get('verifica', '-')}" for it in s["items"])
            telegram.video(chiavi["telegram"], chat_id, video,
                           f"{'✅' if ok else '⚠️ Critic: da controllare'} {s['titolo']}")
            telegram.messaggio(chiavi["telegram"], chat_id,
                               "📋 TITOLO E DESCRIZIONE (copia in Buffer):\n\n" + desc +
                               "\n\n🔎 Fonti dei fatti da controllare prima di pubblicare:\n" + controlli)
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
                       f"🎬 Regista: {fatti}/{quanti} video pronti oggi. Guardali, controlla i fatti e programmali su Buffer.")
    if fatti == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
