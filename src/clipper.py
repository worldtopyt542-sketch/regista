# ==== AUTOCLIPPER: da un video lungo (stream, reaction) a tante clip verticali virali ====
# Sorgenti -> Orecchio (picchi audio) -> Trascrittore (Whisper) -> Talent Scout (Gemini) -> Editor -> Critic -> Telegram
import json, os, shutil, subprocess, sys, traceback, wave
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import datetime, editor, scrittore, sorgenti, telegram, top5
from regista import ARCHIVIO, BOTTONI, CONFIG, RADICE, carica, didascalia, lingue, salva

STATO = os.path.join(RADICE, "clipper.json")
NICCHIA = carica(CONFIG, {}).get("clipper", {}).get("nicchia", "viral videos")

FINESTRA = 70  # secondi di contesto attorno a ogni picco


def pcm(file, sr, inizio=None, durata=None, fmt="s16le"):
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", str(inizio), "-t", str(durata)] if inizio is not None else [])
    return subprocess.Popen(cmd + ["-i", file, "-ac", "1", "-ar", str(sr), "-f", fmt, "-"], stdout=subprocess.PIPE)


def picchi(audio, quanti):
    """Agent ORECCHIO: i momenti piu' rumorosi/agitati (urla, risate, reazioni). Legge a pezzi, poca RAM."""
    sr, db = 8000, []
    p = pcm(audio, sr)
    while True:
        b = p.stdout.read(sr * 2)
        if len(b) < sr:
            break
        a = np.frombuffer(b[:len(b) // 2 * 2], dtype=np.int16).astype(np.float32)
        db.append(20 * np.log10(np.sqrt((a ** 2).mean()) + 1))
    p.wait()
    db = np.array(db)
    if len(db) < 2 * FINESTRA:  # video breve: tutto e' un unico momento
        return [0], len(db)
    liscio = np.convolve(db, np.ones(4) / 4, "same")
    base = np.convolve(db, np.ones(120) / 120, "same")  # rumore di fondo dei 2 minuti attorno
    punteggio = liscio - base + 0.3 * (liscio - db.mean())
    scelti = []
    for t in np.argsort(-punteggio):
        if all(abs(t - s) > FINESTRA for s in scelti):
            scelti.append(int(t))
        if len(scelti) >= quanti:
            break
    return sorted(max(0, t - FINESTRA // 2) for t in scelti), len(db)


def trascrivi(audio, finestre, modello, offset=0):
    """Agent TRASCRITTORE: parole con tempi esatti (assoluti nel video) solo nei momenti candidati."""
    from faster_whisper import WhisperModel
    m = WhisperModel(modello, device="cpu", compute_type="int8")
    out = []
    for t0 in finestre:
        p = pcm(audio, 16000, t0, FINESTRA, "f32le")
        a = np.frombuffer(p.stdout.read(), dtype=np.float32).copy()
        p.wait()
        if len(a) < 16000 * 3:  # finestra vuota (fine del blocco)
            continue
        try:
            segs, _ = m.transcribe(a, word_timestamps=True, vad_filter=True)
            parole = [(offset + t0 + w.start, offset + t0 + w.end, w.word.strip())
                      for s in segs for w in (s.words or [])]
        except Exception as e:
            print(f"   Trascrittore: finestra {t0} saltata ({e})")
            parole = []
        out.append({"inizio": offset + t0, "parole": parole})
    return out


PROMPT = """You are the editor of a viral clip channel (TikTok, YouTube Shorts, Reels): {nicchia}.
Source: "{titolo}" by {canale}.
Below are moments from the stream (absolute seconds). Pick the {k} BEST self-contained clips:
- 12-35 seconds (viral clips that hit millions of views are ~20-30 s); the FIRST 2 seconds must already be
  loud/funny/shocking (no slow intro); end right after the payoff/punchline. No dead air.
- Prefer: shocking or awe moments, peaks of action, funny or quotable lines, wins/fails, never-seen-before details.
- Each clip must make sense without context.
- NEVER pick story spoilers (missions endings, plot twists, character deaths, final missions, credits).
- Avoid moments where copyrighted music is clearly playing loudly.
For each clip write in English: a scroll-stopping overlay hook (max 6 words, no emojis),
a title (max 60 chars, curiosity-driven, not clickbait lies), a 1-sentence description, 5 hashtags.
Score virality 1-100 honestly.
Reply JSON only:
{{"clip": [{{"inizio": 0.0, "fine": 0.0, "punteggio": 0, "hook": "...", "titolo": "...", "descrizione": "...", "hashtags": ["#..."]}}]}}

MOMENTS:
{momenti}"""


def scegli(chiave, src, momenti, k):
    """Agent TALENT SCOUT: Gemini sceglie i pezzi piu' virali."""
    testo = []
    for i, m in enumerate(momenti):
        righe, riga, t = [], [], None
        for a, _, w in m["parole"]:
            t = a if t is None else t
            riga.append(w)
            if len(riga) >= 12:
                righe.append(f"[{t:.1f}] " + " ".join(riga)); riga, t = [], None
        if riga:
            righe.append(f"[{t:.1f}] " + " ".join(riga))
        testo.append(f"--- moment {i + 1} ---\n" + ("\n".join(righe) or "(no speech, loud audio)"))
    prompt = PROMPT.format(nicchia=NICCHIA, titolo=src["titolo"], canale=src["canale"], k=k, momenti="\n".join(testo))
    clip = scrittore.gemini(chiave, prompt, 0.6)["clip"]
    clip = [c for c in clip if 8 <= float(c["fine"]) - float(c["inizio"]) <= 40]
    if not clip:
        raise RuntimeError("Talent Scout: nessuna clip valida")
    return sorted(clip, key=lambda c: -c.get("punteggio", 0))[:k]


COERENZA = """You check a viral Short before posting ({nicchia}). You see 3 frames of the clip and the words spoken in it.
Draft texts: {bozza}
Streamer says: "{parlato}"
Rewrite hook, titolo, descrizione, hashtags so they are 100% coherent with what is VISIBLE in the frames and SAID
in the clip. If the title claims someone finds/does/sees something, it must be in the clip. Keep them
viral and curiosity-driven but never misleading. hook max 6 words; titolo max 60 chars; descrizione 1 sentence;
5 relevant hashtags.
Reply JSON only: {{"hook": "...", "titolo": "...", "descrizione": "...", "hashtags": ["#...", "..."]}}"""


def coerenza(chiave, pezzo, dur, rel, c, lavoro):
    """Agent REVISORE: titolo/gancio/descrizione/hashtag riscritti guardando i fotogrammi veri."""
    immagini = []
    for k, f in enumerate((0.2, 0.5, 0.8)):
        jpg = os.path.join(lavoro, f"f{k}.jpg")
        editor.run(["ffmpeg", "-y", "-ss", f"{dur * f:.1f}", "-i", pezzo, "-frames:v", "1", "-vf", "scale=512:-2", jpg])
        immagini.append((f"Frame {k + 1}:", jpg))
    bozza = json.dumps({k: c.get(k) for k in ("hook", "titolo", "descrizione", "hashtags")}, ensure_ascii=False)
    try:
        r = scrittore.gemini(chiave, COERENZA.format(nicchia=NICCHIA, bozza=bozza, parlato=" ".join(w for *_, w in rel)[:1500]),
                             0.5, immagini)
        c.update({k: r[k] for k in ("hook", "titolo", "descrizione", "hashtags") if r.get(k)})
    except Exception as e:
        print("   Revisore: salto", e)


def frasi(rel, dur):
    """Parole -> frasi brevi (pausa > 0.6 s o 7 parole); ogni frase resta fino all'inizio della successiva."""
    gr, cur = [], []
    for a, b, w in rel:
        if cur and (len(cur) >= 7 or a - cur[-1][1] > 0.6):
            gr.append(cur); cur = []
        cur.append((a, b, w))
    if cur:
        gr.append(cur)
    return [(g[0][0], gr[i + 1][0][0] if i + 1 < len(gr) else dur, " ".join(x[2] for x in g)) for i, g in enumerate(gr)]


def monta(pezzo, dur, gruppi, hook, credito, out, lavoro, font=None, cap=84):
    """Agent EDITOR: 9:16 con sfondo sfocato, sottotitoli, gancio in alto."""
    ass = os.path.join(lavoro, "sub.ass")
    editor.scrivi_ass(ass, gruppi, "", dur, credito, hook, font, cap)
    fc = ("[0:v]split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
          "boxblur=25:3,eq=brightness=-0.2[bg];[b]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
          f"[bg][fg]overlay=(W-w)/2:'if(lt(h,1100),(H-h)/2-120,(H-h)/2)',fps=30,setsar=1,{editor.ass_filtro(ass)}[v]")
    editor.run(["ffmpeg", "-y", "-i", pezzo, "-t", f"{dur:.2f}", "-filter_complex", fc, "-map", "[v]",
                "-map", "0:a:0", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:v", "libx264", "-preset",
                "veryfast", "-crf", "21", "-maxrate", "3M", "-bufsize", "6M", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out])


def lavora(url, cfg, chiavi, chat_id, arch, k):
    src = sorgenti.info(url)
    if "youtube" in url:
        src["canale"] = f"{src['canale']} (CC BY)"
    blocco = cfg.get("ore_per_blocco", 4) * 3600
    inizio = arch.setdefault("avanzamento", {}).get(url, 0)
    fine = min(inizio + blocco, src["durata"] or inizio + blocco)
    arch["avanzamento"][url] = fine
    print(f"\n=== {src['titolo']} ({src['canale']}, {src['durata'] // 60} min) blocco {inizio // 3600:.0f}-{fine / 3600:.1f} h")
    lavoro = os.path.join(RADICE, "lavoro", "clip")
    shutil.rmtree(lavoro, ignore_errors=True); os.makedirs(lavoro)
    editor.WORK = lavoro
    audio = sorgenti.scarica_audio(url, os.path.join(lavoro, "audio"), inizio, fine)
    finestre, _ = picchi(audio, cfg.get("momenti_candidati", 14))
    os.environ.setdefault("OMP_NUM_THREADS", "4")
    momenti = trascrivi(audio, finestre, cfg.get("whisper", "small"), offset=inizio)
    clip = scegli(chiavi["gemini"], src, momenti, k)
    tutte = [p for m in momenti for p in m["parole"]]
    L = lingue(carica(CONFIG, {}))
    fatte = 0
    for n, c in enumerate(clip):
        c["inizio"], c["fine"] = float(c["inizio"]), float(c["fine"])
        dur = c["fine"] - c["inizio"]
        try:
            pezzo = sorgenti.scarica_pezzo(url, c["inizio"], c["fine"], os.path.join(lavoro, f"raw{n}.mp4"))
            rel = [(a - c["inizio"], b - c["inizio"], w) for a, b, w in tutte if c["inizio"] <= a < c["fine"]]
            coerenza(chiavi["gemini"], pezzo, dur, rel, c, lavoro)
            fr = frasi(rel, dur)
            base = {"titolo": c["titolo"], "hook": c.get("hook", ""), "descrizione": c.get("descrizione", ""),
                    "hashtags": c.get("hashtags") or ["#shorts"], "frasi": [f[2] for f in fr]}
            trad = scrittore.traduci(chiavi["gemini"], base, {k: v["nome"] for k, v in L.items() if k != "en"})
            trad["en"] = base
            for cod, lg in L.items():
                t = trad[cod]
                if cod == "en":  # originale: karaoke parola per parola
                    gruppi, cap = editor.gruppi_parole(rel, " ".join(w for *_, w in rel) or " ", dur), 84
                else:  # tradotto: frase intera sincronizzata
                    gruppi, cap = [[(a, b, t["frasi"][i])] for i, (a, b, _) in enumerate(fr)], 64
                out = os.path.join(RADICE, "output", f"{src['id'].replace(':', '_')}_{n + 1}_{cod}.mp4")
                os.makedirs(os.path.dirname(out), exist_ok=True)
                monta(pezzo, dur, gruppi, t["hook"], "Clip: " + src["canale"], out, lavoro, lg.get("font"), cap)
                editor.marchia(out, out + ".m.mp4"); os.replace(out + ".m.mp4", out)
                ok = editor.critic(out, max_sec=40)
                cap_txt = didascalia(t, cod, src["canale"], f"{c['punteggio']}/100" + ("" if ok else " · critic ⚠️"))
                telegram.video(chiavi["telegram"], chat_id, out, cap_txt + f"\n{url}", bottoni=BOTTONI)
                os.remove(out)
            fatte += 1
        except Exception as e:
            traceback.print_exc()
            telegram.messaggio(chiavi["telegram"], chat_id, f"❌ Clip {n + 1} non riuscita: {str(e)[:300]}")
    oggi = datetime.date.today().isoformat()
    fatti_top = arch.setdefault("top5", {}).get(oggi, 0)
    if fatti_top < cfg.get("top5_al_giorno", 2):
        try:
            video, t = top5.crea(url, src, momenti, tutte, chiavi["gemini"], lavoro, "", L["en"]["voce"], NICCHIA)
            editor.marchia(video, video + ".m.mp4"); os.replace(video + ".m.mp4", video)
            ok = editor.critic(video, max_sec=50)
            telegram.video(chiavi["telegram"], chat_id, video,
                           didascalia(t, "en", src["canale"], "TOP 5" + ("" if ok else " · critic ⚠️")) + f"\n{url}",
                           bottoni=BOTTONI)
            arch["top5"] = {oggi: fatti_top + 1}
        except Exception as e:
            traceback.print_exc()
            telegram.messaggio(chiavi["telegram"], chat_id, f"❌ Top 5 non riuscita: {str(e)[:300]}")
    if fine >= (src["durata"] or 0):
        arch["sorgenti_fatte"].append(src["id"])
    arch.setdefault("storico_clip", []).append({"fonte": src["id"], "titolo": src["titolo"], "clip": fatte})
    shutil.rmtree(lavoro, ignore_errors=True)
    return fatte


def main():
    cfg = carica(CONFIG, {}).get("clipper", {})
    arch = carica(STATO, {"sorgenti_fatte": [], "url_fatti": []})
    chiavi = {"gemini": os.environ.get("GEMINI_API_KEY"), "telegram": os.environ.get("TELEGRAM_BOT_TOKEN")}
    if not all(chiavi.values()):
        sys.exit("Mancano i secret GEMINI_API_KEY / TELEGRAM_BOT_TOKEN")
    chat_id = carica(ARCHIVIO, {}).get("chat_id") or telegram.trova_chat_id(chiavi["telegram"])
    coda = [u for u in (os.environ.get("URL") or "").split() if u]
    coda += carica(os.path.join(RADICE, "pubblica.json"), {}).get("coda_link", [])
    if cfg.get("canali"):
        coda += sorgenti.da_canali(cfg["canali"], cfg.get("parole_chiave", ["gta"]), arch["url_fatti"])
    if cfg.get("ricerche"):
        import scopri
        if not os.environ.get("YOUTUBE_API_KEY"):
            telegram.messaggio(chiavi["telegram"], chat_id, "⚠️ Manca il secret YOUTUBE_API_KEY: non posso cercare video virali CC.")
        else:
            coda += [t["url"] for t in scopri.cerca(os.environ["YOUTUBE_API_KEY"], cfg["ricerche"], arch["url_fatti"],
                                                    cfg.get("min_views", 1_000_000), cfg.get("video_per_giro", 4))]
    in_corso = [u for u, t in arch.get("avanzamento", {}).items() if u not in arch["url_fatti"]]
    coda = [u for u in dict.fromkeys(in_corso + coda) if u not in arch["url_fatti"]][:cfg.get("video_per_giro", 2)]
    if not coda:
        print("Niente di nuovo da clippare."); return
    totale = 0
    obiettivo = cfg.get("clip_al_giorno", 8)
    for url in coda:
        if totale >= obiettivo:
            break
        try:
            totale += lavora(url, cfg, chiavi, chat_id, arch, min(cfg.get("clip_per_video", 4), obiettivo - totale))
            if arch.get("avanzamento", {}).get(url, 0) >= (sorgenti.info(url)["durata"] or 0):
                arch["url_fatti"].append(url)
        except Exception as e:
            traceback.print_exc()
            arch["url_fatti"].append(url)
            telegram.messaggio(chiavi["telegram"], chat_id, f"❌ Non riesco a clippare {url}: {str(e)[:300]}")
        arch["url_fatti"] = arch["url_fatti"][-500:]
        salva(STATO, arch)
    telegram.messaggio(chiavi["telegram"], chat_id, f"☀️ Buongiorno! {totale} clip + {arch.get('top5', {}).get(datetime.date.today().isoformat(), 0)} Top 5 pronte qui sopra. Premi ✅ per pubblicarle su TikTok, Instagram e YouTube Shorts.")


if __name__ == "__main__":
    main()
