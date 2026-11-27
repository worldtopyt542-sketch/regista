# ==== AUTOCLIPPER Planet Off Scale: da un video lungo CC BY a tante clip verticali, in piu' lingue ====
# Sorgenti (licenza verificata) -> Orecchio + Occhio (picchi audio e cambi scena) -> Trascrittore (Whisper)
# -> Talent Scout (Gemini, testo + fotogrammi) -> Revisore -> Editor (1 sola codifica) -> Critic -> Telegram (gruppo)
import json, os, shutil, subprocess, sys, traceback
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import datetime, comune, editor, scopri, scrittore, sorgenti, telegram, top5
from comune import ARCHIVIO, CONFIG, RADICE, carica, didascalia, lingue, salva

STATO = os.path.join(RADICE, "clipper.json")
BRAND = comune.brand()
NICCHIA = BRAND["nicchia"]
TENTATIVI_MAX = 3  # errori temporanei (Gemini 429, rete) prima di abbandonare un video

FINESTRA = 70  # secondi di contesto attorno a ogni picco


def pcm(file, sr, inizio=None, durata=None, fmt="s16le"):
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", str(inizio), "-t", str(durata)] if inizio is not None else [])
    return subprocess.Popen(cmd + ["-i", file, "-ac", "1", "-ar", str(sr), "-f", fmt, "-"], stdout=subprocess.PIPE)


def volume_db(audio):
    """dB al secondo, letto a pezzi (poca RAM)."""
    sr, db = 8000, []
    p = pcm(audio, sr)
    while True:
        b = p.stdout.read(sr * 2)
        if len(b) < sr:
            break
        a = np.frombuffer(b[:len(b) // 2 * 2], dtype=np.int16).astype(np.float32)
        db.append(20 * np.log10(np.sqrt((a ** 2).mean()) + 1))
    p.wait()
    return np.array(db)


def movimento(video, secondi):
    """Agent OCCHIO: quanta 'azione' c'e' in ogni secondo (cambi scena + movimento), dal video a bassa risoluzione.
    Serve ai video di natura/spazio dove l'audio e' musica costante e il volume non dice niente."""
    if not video:
        return None
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", video, "-vf", "fps=2,scale=160:-2,select='gte(scene,0)',"
                        "metadata=print:key=lavfi.scene_score", "-an", "-f", "null", "-"],
                       capture_output=True, text=True)
    punti = np.zeros(max(1, secondi))
    t = None
    for riga in r.stderr.splitlines():
        if "pts_time:" in riga:
            try:
                t = int(float(riga.split("pts_time:")[1].split()[0]))
            except ValueError:
                t = None
        elif "scene_score=" in riga and t is not None and t < len(punti):
            punti[t] += float(riga.split("scene_score=")[1])
    return punti if punti.any() else None


def picchi(audio, quanti, video=None):
    """I momenti piu' forti: volume relativo (urla, boati, esplosioni) + azione visiva (lanci, attacchi, crolli)."""
    db = volume_db(audio)
    if len(db) < 2 * FINESTRA:  # video breve: tutto e' un unico momento
        return [0], len(db)
    liscio = np.convolve(db, np.ones(4) / 4, "same")
    base = np.convolve(db, np.ones(120) / 120, "same")  # rumore di fondo dei 2 minuti attorno
    punteggio = liscio - base + 0.3 * (liscio - db.mean())
    mov = movimento(video, len(db))
    if mov is not None:
        mov = np.convolve(mov[:len(db)], np.ones(6) / 6, "same")
        z = lambda x: (x - x.mean()) / (x.std() + 1e-6)
        punteggio = z(punteggio) + z(mov)  # stesso peso a orecchio e occhio
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


PROMPT = """You are the editor of a viral Shorts/Reels/TikTok channel: {nicchia}.
Source video (Creative Commons): "{titolo}" by {canale}.
Below are candidate moments (absolute seconds): what is said, plus 2 frames of each moment.
Pick the {k} BEST self-contained clips:
- 12-35 seconds; the FIRST 2 seconds must already show the most striking image or action (no slow intro,
  no title cards, no talking head); end right after the payoff (launch, catch, impact, reveal). No dead air.
- Prefer: sheer scale (huge/tiny), raw power of nature, rare animal behaviour, rocket launches and space views,
  "how is this real" moments, near misses, satisfying perfect timing.
- Each clip must make sense without context. Avoid moments with intros/outros, sponsor reads, logos of other
  channels, watermarks or on-screen text from the original, and loud copyrighted music.
For each clip write in English: a scroll-stopping overlay hook (max 6 words, no emojis, curiosity or scale,
never a lie), a title (max 60 chars), a 1-sentence description with one surprising real fact if you know it
for sure, 5 hashtags. Score virality 1-100 honestly (most clips are 40-70).
Reply JSON only:
{{"clip": [{{"inizio": 0.0, "fine": 0.0, "punteggio": 0, "hook": "...", "titolo": "...", "descrizione": "...", "hashtags": ["#..."]}}]}}

MOMENTS:
{momenti}"""


def fotogrammi(video, istanti, lavoro, nome):
    """JPG piccoli dal video a bassa risoluzione: Gemini *vede* i momenti invece di indovinarli dal parlato."""
    out = []
    for i, t in enumerate(istanti):
        jpg = os.path.join(lavoro, f"{nome}{i}.jpg")
        try:
            editor.run(["ffmpeg", "-y", "-ss", f"{max(0, t):.1f}", "-i", video, "-frames:v", "1", "-vf", "scale=320:-2", jpg])
            if os.path.exists(jpg):
                out.append(jpg)
        except RuntimeError:
            pass
    return out


def scegli(chiave, src, momenti, k, video=None, inizio_blocco=0, lavoro=""):
    """Agent TALENT SCOUT: Gemini sceglie i pezzi piu' virali guardando parlato e fotogrammi."""
    testo, immagini = [], []
    for i, m in enumerate(momenti):
        righe, riga, t = [], [], None
        for a, _, w in m["parole"]:
            t = a if t is None else t
            riga.append(w)
            if len(riga) >= 12:
                righe.append(f"[{t:.1f}] " + " ".join(riga)); riga, t = [], None
        if riga:
            righe.append(f"[{t:.1f}] " + " ".join(riga))
        testo.append(f"--- moment {i + 1} (starts {m['inizio']:.0f}) ---\n" + ("\n".join(righe) or "(no speech)"))
        if video:
            rel = m["inizio"] - inizio_blocco
            for j, jpg in enumerate(fotogrammi(video, (rel + 20, rel + 45), lavoro, f"m{i}_")):
                immagini.append((f"Moment {i + 1}, frame at {m['inizio'] + (20, 45)[j]:.0f} s:", jpg))
    prompt = PROMPT.format(nicchia=NICCHIA, titolo=src["titolo"], canale=src["canale"], k=k, momenti="\n".join(testo))
    clip = scrittore.gemini(chiave, prompt, 0.6, immagini or None)["clip"]
    clip = [c for c in clip if 8 <= float(c["fine"]) - float(c["inizio"]) <= 40]
    if not clip:
        raise RuntimeError("Talent Scout: nessuna clip valida")
    return sorted(clip, key=lambda c: -c.get("punteggio", 0))[:k]


COERENZA = """You check a viral Short before posting ({nicchia}). You see 3 frames of the clip and the words spoken in it.
Draft texts: {bozza}
Spoken in the clip: "{parlato}"
Rewrite hook, titolo, descrizione, hashtags so they are 100% coherent with what is VISIBLE in the frames and SAID
in the clip. If the title claims something happens, it must be in the clip. Name the animal / rocket / place only
if you are sure. Keep them viral and curiosity-driven (scale, power, rarity) but never misleading.
hook max 6 words; titolo max 60 chars; descrizione 1 sentence; 5 relevant hashtags.
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


def monta(pezzo, dur, gruppi, hook, credito, out, lavoro, font=None, cap=84, cta=""):
    """Agent EDITOR: 9:16 con sfondo sfocato, sottotitoli, gancio, invito finale, logo e barra.
    Tutto in UNA codifica (prima erano due: monta + marchia), quindi circa meta' del tempo di CPU per lingua."""
    ass = os.path.join(lavoro, "sub.ass")
    editor.scrivi_ass(ass, gruppi, "", dur, credito, hook, font, cap, cta=cta)
    fc = ("[0:v]split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
          "boxblur=25:3,eq=brightness=-0.2[bg];[b]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
          f"[bg][fg]overlay=(W-w)/2:'if(lt(h,1100),(H-h)/2-120,(H-h)/2)',fps=30,setsar=1,{editor.ass_filtro(ass)}[base];"
          + editor.filtro_marchio(dur, "[base]", "[1:v]", "[v]"))
    editor.run(["ffmpeg", "-y", "-i", pezzo, "-i", editor.logo_path(), "-t", f"{dur:.2f}", "-filter_complex", fc,
                "-map", "[v]", "-map", "0:a:0?", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:v", "libx264", "-preset",
                "veryfast", "-crf", "21", "-maxrate", "3M", "-bufsize", "6M", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out])


def scarica_video_leggero(url, dest, inizio, fine):
    """Video a 240p del blocco, solo per guardare (cambi scena + fotogrammi per Gemini). Facoltativo."""
    import glob
    try:
        sorgenti._yt(["-f", "wv*[height>=144]/bv*[height<=240]/w", "--download-sections", f"*{inizio:.0f}-{fine:.0f}",
                      "-o", dest + ".%(ext)s", url])
        return sorted(glob.glob(dest + ".*"))[0]
    except Exception as e:
        print("   Occhio: video leggero non disponibile, uso solo l'audio", str(e)[:150])
        return None


def lavora(url, cfg, chiavi, chat_id, arch, k):
    fonte = scopri.verifica(chiavi.get("youtube"), url)  # LicenzaNonLibera = errore definitivo
    src = sorgenti.info(url)
    src["canale"] = f"{fonte['autore'] or src['canale']} ({fonte['licenza']})"
    fonte["titolo"] = fonte.get("titolo") or src["titolo"]
    blocco = cfg.get("ore_per_blocco", 3) * 3600
    inizio = arch.setdefault("avanzamento", {}).get(url, 0)
    fine = min(inizio + blocco, src["durata"] or inizio + blocco)
    print(f"\n=== {src['titolo']} ({src['canale']}, {src['durata'] // 60} min) blocco {inizio // 3600:.0f}-{fine / 3600:.1f} h")
    lavoro = os.path.join(RADICE, "lavoro", "clip")
    shutil.rmtree(lavoro, ignore_errors=True); os.makedirs(lavoro)
    editor.WORK = lavoro
    audio = sorgenti.scarica_audio(url, os.path.join(lavoro, "audio"), inizio, fine)
    leggero = scarica_video_leggero(url, os.path.join(lavoro, "leggero"), inizio, fine)
    finestre, _ = picchi(audio, cfg.get("momenti_candidati", 14), leggero)
    os.environ.setdefault("OMP_NUM_THREADS", "4")
    momenti = trascrivi(audio, finestre, cfg.get("whisper", "small"), offset=inizio)
    clip = scegli(chiavi["gemini"], src, momenti, k, leggero, inizio, lavoro)
    tutte = [p for m in momenti for p in m["parole"]]
    tutta_cfg = carica(CONFIG, {})
    L = lingue(tutta_cfg)
    soglia = comune.soglia_auto(tutta_cfg)
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
                    "hashtags": c.get("hashtags") or [], "frasi": [f[2] for f in fr]}
            trad = scrittore.traduci(chiavi["gemini"], base, {k: v["nome"] for k, v in L.items() if k != "en"})
            trad["en"] = base
            gruppo = {"id": comune.nuovo_gruppo(), "creato": datetime.datetime.utcnow().isoformat(), "formato": "clip",
                      "titolo": base["titolo"], "punteggio": int(c.get("punteggio", 0)), "fonte": fonte, "versioni": {}}
            video, tutti_ok = {}, True
            for cod, lg in L.items():
                t = trad[cod]
                if cod == "en":  # originale: karaoke parola per parola
                    gruppi_sub, cap = editor.gruppi_parole(rel, " ".join(w for *_, w in rel) or " ", dur), 84
                else:  # tradotto: frase intera sincronizzata
                    gruppi_sub, cap = [[(a, b, t["frasi"][i])] for i, (a, b, _) in enumerate(fr)], 64
                out = os.path.join(RADICE, "output", f"{src['id'].replace(':', '_')}_{n + 1}_{cod}.mp4")
                os.makedirs(os.path.dirname(out), exist_ok=True)
                monta(pezzo, dur, gruppi_sub, t["hook"], "Clip: " + src["canale"], out, lavoro, lg.get("font"), cap,
                      comune.cta(cod, tutta_cfg))
                ok = editor.critic(out, max_sec=40)
                tutti_ok &= ok
                gruppo["versioni"][cod] = {"titolo": t["titolo"], "descrizione": t.get("descrizione", ""),
                                           "hashtags": comune.hashtag(t, tutta_cfg)}
                video[cod] = (out, didascalia(t, cod, src["canale"], f"{c['punteggio']}/100" + ("" if ok else " · critic ⚠️")))
            gruppo["critic_ok"] = tutti_ok
            gruppo["auto"] = bool(soglia and tutti_ok and gruppo["punteggio"] >= soglia)
            telegram.invia_gruppo(chiavi["telegram"], chat_id, gruppo, video,
                                  f"{gruppo['punteggio']}/100 · {fonte['url']}")
            comune.salva_gruppo(gruppo)
            for out, _ in video.values():
                os.remove(out)
            fatte += 1
        except Exception as e:
            traceback.print_exc()
            telegram.messaggio(chiavi["telegram"], chat_id, f"❌ Clip {n + 1} non riuscita: {str(e)[:300]}")
    oggi = datetime.date.today().isoformat()
    fatti_top = arch.setdefault("top5", {}).get(oggi, 0)
    if fatti_top < cfg.get("top5_al_giorno", 2):
        try:
            crea_top5(url, src, fonte, momenti, tutte, chiavi, chat_id, lavoro, L, tutta_cfg)
            arch["top5"] = {oggi: fatti_top + 1}
        except Exception as e:
            traceback.print_exc()
            telegram.messaggio(chiavi["telegram"], chat_id, f"❌ Top 5 non riuscita: {str(e)[:300]}")
    arch["avanzamento"][url] = fine  # il blocco avanza solo quando e' stato lavorato davvero
    if fine >= (src["durata"] or 0):
        arch["sorgenti_fatte"].append(src["id"])
    arch.setdefault("storico_clip", []).append({"fonte": src["id"], "titolo": src["titolo"], "clip": fatte})
    arch["storico_clip"] = arch["storico_clip"][-300:]
    shutil.rmtree(lavoro, ignore_errors=True)
    return fatte, fine >= (src["durata"] or 0)


def crea_top5(url, src, fonte, momenti, tutte, chiavi, chat_id, lavoro, L, cfg):
    """Top 5 in inglese (voce narrante); le altre lingue arriveranno quando la voce sara' tradotta per segmento."""
    video, t = top5.crea(url, src, momenti, tutte, chiavi["gemini"], lavoro, L["en"]["voce"], NICCHIA,
                         BRAND["tono"], comune.cta("en", cfg))
    editor.marchia(video, video + ".m.mp4"); os.replace(video + ".m.mp4", video)
    ok = editor.critic(video, max_sec=50)
    gruppo = {"id": comune.nuovo_gruppo(), "creato": datetime.datetime.utcnow().isoformat(), "formato": "top5",
              "titolo": t["titolo"], "punteggio": 0, "fonte": fonte, "critic_ok": ok, "auto": False,
              "versioni": {"en": {"titolo": t["titolo"], "descrizione": t.get("descrizione", ""),
                                  "hashtags": comune.hashtag(t, cfg)}}}
    telegram.invia_gruppo(chiavi["telegram"], chat_id, gruppo,
                          {"en": (video, didascalia(t, "en", src["canale"], "TOP 5" + ("" if ok else " · critic ⚠️")))},
                          f"TOP 5 · {fonte['url']}")
    comune.salva_gruppo(gruppo)


def main():
    cfg = carica(CONFIG, {}).get("clipper", {})
    arch = carica(STATO, {"sorgenti_fatte": [], "url_fatti": []})
    chiavi = {"gemini": os.environ.get("GEMINI_API_KEY"), "telegram": os.environ.get("TELEGRAM_BOT_TOKEN"),
              "youtube": os.environ.get("YOUTUBE_API_KEY")}
    if not (chiavi["gemini"] and chiavi["telegram"]):
        sys.exit("Mancano i secret GEMINI_API_KEY / TELEGRAM_BOT_TOKEN")
    chat_id = carica(ARCHIVIO, {}).get("chat_id") or telegram.trova_chat_id(chiavi["telegram"])
    comune.pulisci_gruppi()
    coda = [u for u in (os.environ.get("URL") or "").split() if u]
    coda += carica(os.path.join(RADICE, "pubblica.json"), {}).get("coda_link", [])
    if cfg.get("ricerche"):
        if not chiavi["youtube"]:
            telegram.messaggio(chiavi["telegram"], chat_id, "⚠️ Manca il secret YOUTUBE_API_KEY: non posso cercare video virali CC.")
        else:
            coda += [t["url"] for t in scopri.cerca(chiavi["youtube"], cfg["ricerche"], arch["url_fatti"],
                                                    cfg.get("min_views", 1_000_000), cfg.get("video_per_giro", 4))]
    in_corso = [u for u, t in arch.get("avanzamento", {}).items() if u not in arch["url_fatti"]]
    coda = [u for u in dict.fromkeys(in_corso + coda) if u not in arch["url_fatti"]][:cfg.get("video_per_giro", 2)]
    if not coda:
        print("Niente di nuovo da clippare."); return
    totale = 0
    obiettivo = cfg.get("clip_al_giorno", 8)
    tentativi = arch.setdefault("tentativi", {})
    for url in coda:
        if totale >= obiettivo:
            break
        try:
            fatte, finito = lavora(url, cfg, chiavi, chat_id, arch, min(cfg.get("clip_per_video", 4), obiettivo - totale))
            totale += fatte
            tentativi.pop(url, None)
            if finito:
                arch["url_fatti"].append(url)
        except scopri.LicenzaNonLibera as e:  # definitivo: non si riprova
            arch["url_fatti"].append(url)
            telegram.messaggio(chiavi["telegram"], chat_id, f"🚫 Scartato {url}: {e}")
        except Exception as e:  # temporaneo (Gemini 429, rete, yt-dlp): riprova al prossimo giro
            traceback.print_exc()
            tentativi[url] = tentativi.get(url, 0) + 1
            if tentativi[url] >= TENTATIVI_MAX:
                arch["url_fatti"].append(url)
                tentativi.pop(url, None)
            telegram.messaggio(chiavi["telegram"], chat_id,
                               f"❌ Non riesco a clippare {url} (tentativo {tentativi.get(url, TENTATIVI_MAX)}/{TENTATIVI_MAX}): {str(e)[:300]}")
        arch["url_fatti"] = arch["url_fatti"][-500:]
        salva(STATO, arch)
    telegram.messaggio(chiavi["telegram"], chat_id, f"☀️ Buongiorno! {totale} clip + {arch.get('top5', {}).get(datetime.date.today().isoformat(), 0)} Top 5 pronte qui sopra. Un ✅ pubblica tutte le lingue della clip su TikTok, Instagram e YouTube Shorts.")


if __name__ == "__main__":
    main()
