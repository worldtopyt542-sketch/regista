# ==== AUTOCLIPPER: da un video lungo (stream, reaction) a tante clip verticali virali ====
# Sorgenti -> Orecchio (picchi audio) -> Trascrittore (Whisper) -> Talent Scout (Gemini) -> Editor -> Critic -> Telegram
import json, os, shutil, subprocess, sys, traceback, wave
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import editor, scrittore, sorgenti, telegram
from regista import ARCHIVIO, CONFIG, RADICE, carica, salva

FINESTRA = 70  # secondi di contesto attorno a ogni picco


def picchi(wav, quanti):
    """Agent ORECCHIO: i momenti piu' rumorosi/agitati (urla, risate, reazioni)."""
    with wave.open(wav) as w:
        sr = w.getframerate()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    sec = len(a) // sr
    rms = np.sqrt((a[:sec * sr].reshape(sec, sr) ** 2).mean(1)) + 1
    db = 20 * np.log10(rms)
    liscio = np.convolve(db, np.ones(4) / 4, "same")
    base = np.convolve(db, np.ones(120) / 120, "same")  # rumore di fondo dei 2 minuti attorno
    punteggio = liscio - base + 0.3 * (liscio - db.mean())
    scelti = []
    for t in np.argsort(-punteggio):
        if all(abs(t - s) > FINESTRA for s in scelti):
            scelti.append(int(t))
        if len(scelti) >= quanti:
            break
    return sorted(max(0, t - FINESTRA // 2) for t in scelti), sec


def trascrivi(wav, finestre, modello):
    """Agent TRASCRITTORE: parole con tempi esatti solo nei momenti candidati."""
    from faster_whisper import WhisperModel
    m = WhisperModel(modello, device="cpu", compute_type="int8")
    out = []
    for i, t0 in enumerate(finestre):
        tmp = wav + f".{i}.wav"
        editor.run(["ffmpeg", "-y", "-ss", str(t0), "-t", str(FINESTRA), "-i", wav, tmp])
        segs, _ = m.transcribe(tmp, word_timestamps=True, vad_filter=True)
        parole = [(t0 + w.start, t0 + w.end, w.word.strip()) for s in segs for w in (s.words or [])]
        out.append({"inizio": t0, "parole": parole})
        os.remove(tmp)
    return out


PROMPT = """You are the editor of a viral clip channel (TikTok, YouTube Shorts, Reels) about streamers and GTA 6.
Source: "{titolo}" by {canale}.
Below are moments from the stream (absolute seconds). Pick the {k} BEST self-contained clips:
- 15-50 seconds; start right before the setup, end right after the payoff/punchline. No dead air.
- Prefer: loud reactions, funny lines, shock, rage, wins/fails, quotable sentences, GTA 6 discoveries.
- Each clip must make sense without context.
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
    prompt = PROMPT.format(titolo=src["titolo"], canale=src["canale"], k=k, momenti="\n".join(testo))
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.6, "responseMimeType": "application/json"}}
    errori = []
    for m in scrittore.modelli_candidati(chiave, scrittore.ULTIMO_BUONO):
        try:
            r = scrittore._post(f"{scrittore.BASE}models/{m}:generateContent?key={chiave}", body)
            clip = scrittore.estrai_json(r["candidates"][0]["content"]["parts"][0]["text"])["clip"]
            clip = [c for c in clip if 8 <= float(c["fine"]) - float(c["inizio"]) <= 60]
            if clip:
                scrittore.ULTIMO_BUONO = m
                return sorted(clip, key=lambda c: -c.get("punteggio", 0))[:k]
        except Exception as e:
            errori.append(f"{m}: {str(e)[:80]}")
    raise RuntimeError("Talent Scout: nessun modello ha risposto. " + " | ".join(errori[-3:]))


def monta(pezzo, c, parole, credito, out, lavoro):
    """Agent EDITOR: 9:16 con sfondo sfocato, sottotitoli parola per parola, gancio in alto."""
    dur = float(c["fine"]) - float(c["inizio"])
    rel = [(a - c["inizio"], b - c["inizio"], w) for a, b, w in parole if c["inizio"] <= a < c["fine"]]
    ass = os.path.join(lavoro, "sub.ass")
    editor.scrivi_ass(ass, editor.gruppi_parole(rel, " ".join(w for *_, w in rel) or " ", dur),
                      "", dur, credito, c.get("hook", ""))
    fc = ("[0:v]split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
          "boxblur=25:3,eq=brightness=-0.2[bg];[b]scale=1080:-2[fg];"
          f"[bg][fg]overlay=(W-w)/2:(H-h)/2-120,fps=30,setsar=1,ass={ass}[v]")
    editor.run(["ffmpeg", "-y", "-i", pezzo, "-t", f"{dur:.2f}", "-filter_complex", fc, "-map", "[v]",
                "-map", "0:a:0", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:v", "libx264", "-preset",
                "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                "-movflags", "+faststart", out])


def lavora(url, cfg, chiavi, chat_id, arch):
    src = sorgenti.info(url)
    if src["id"] in arch.setdefault("sorgenti_fatte", []):
        print("   gia' clippato, salto"); return 0
    print(f"\n=== {src['titolo']} ({src['canale']}, {src['durata'] // 60} min)")
    lavoro = os.path.join(RADICE, "lavoro", "clip")
    shutil.rmtree(lavoro, ignore_errors=True); os.makedirs(lavoro)
    editor.WORK = lavoro
    wav = sorgenti.scarica_audio(url, os.path.join(lavoro, "audio"))
    finestre, _ = picchi(wav, cfg.get("momenti_candidati", 14))
    momenti = trascrivi(wav, finestre, cfg.get("whisper", "small"))
    clip = scegli(chiavi["gemini"], src, momenti, cfg.get("clip_per_video", 6))
    tutte = [p for m in momenti for p in m["parole"]]
    fatte = 0
    for n, c in enumerate(clip):
        c["inizio"], c["fine"] = float(c["inizio"]), float(c["fine"])
        try:
            pezzo = sorgenti.scarica_pezzo(url, c["inizio"], c["fine"], os.path.join(lavoro, f"raw{n}.mp4"))
            out = os.path.join(RADICE, "output", f"{src['id'].replace(':', '_')}_{n + 1}.mp4")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            monta(pezzo, c, tutte, "Clip: " + src["canale"], out, lavoro)
            ok = editor.critic(out, max_sec=60)
            telegram.video(chiavi["telegram"], chat_id, out,
                           f"{'✅' if ok else '⚠️'} {c['punteggio']}/100 · {c['titolo']}")
            telegram.messaggio(chiavi["telegram"], chat_id,
                               f"{c['titolo']}\n\n{c.get('descrizione', '')}\n\n{' '.join(c.get('hashtags', []))}"
                               f"\n\nSource: {src['canale']} — {url}")
            fatte += 1
        except Exception as e:
            traceback.print_exc()
            telegram.messaggio(chiavi["telegram"], chat_id, f"❌ Clip {n + 1} non riuscita: {str(e)[:300]}")
    arch["sorgenti_fatte"].append(src["id"])
    arch.setdefault("storico_clip", []).append({"fonte": src["id"], "titolo": src["titolo"], "clip": fatte})
    shutil.rmtree(lavoro, ignore_errors=True)
    return fatte


def main():
    cfg = carica(CONFIG, {}).get("clipper", {})
    arch = carica(ARCHIVIO, {})
    chiavi = {"gemini": os.environ.get("GEMINI_API_KEY"), "telegram": os.environ.get("TELEGRAM_BOT_TOKEN")}
    if not all(chiavi.values()):
        sys.exit("Mancano i secret GEMINI_API_KEY / TELEGRAM_BOT_TOKEN")
    chat_id = arch.get("chat_id") or telegram.trova_chat_id(chiavi["telegram"])
    arch["chat_id"] = chat_id
    coda = [u for u in (os.environ.get("URL") or "").split() if u]
    coda += sorgenti.da_telegram(chiavi["telegram"], chat_id, arch)
    if cfg.get("canali"):
        coda += sorgenti.da_canali(cfg["canali"], cfg.get("parole_chiave", ["gta"]), arch.get("sorgenti_fatte", []))
    coda = list(dict.fromkeys(coda))[:cfg.get("video_per_giro", 3)]
    salva(ARCHIVIO, arch)
    if not coda:
        print("Niente di nuovo da clippare."); return
    totale = 0
    for url in coda:
        try:
            totale += lavora(url, cfg, chiavi, chat_id, arch)
        except Exception as e:
            traceback.print_exc()
            telegram.messaggio(chiavi["telegram"], chat_id, f"❌ Non riesco a clippare {url}: {str(e)[:300]}")
        salva(ARCHIVIO, arch)
    telegram.messaggio(chiavi["telegram"], chat_id, f"🎬 Autoclipper: {totale} clip pronte da {len(coda)} video.")


if __name__ == "__main__":
    main()
