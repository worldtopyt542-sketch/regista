# ==== AGENT TOP 5: compilation dei momenti piu' virali di una live, con voce narrante coerente ====
# Talent Scout sceglie 5 momenti -> Osservatore (Gemini guarda i fotogrammi) scrive la voce -> montaggio
import os
import editor, scrittore, sorgenti

SCELTA = """You make viral YouTube Shorts / TikToks ({nicchia}): "Top 5" countdowns of the most jaw-dropping moments of a video.
Source (Creative Commons): "{titolo}" by {canale}.
From the moments below (absolute seconds, transcript of what is said), pick 5 DIFFERENT moments, each 5-8 seconds
(the whole Short must stay under 45 s). Choose the most striking: sheer scale, raw power, rare behaviour, perfect
timing, "how is this real". Order from #5 to #1 (best last). Pick ONE clear angle for the list (e.g. "biggest",
"closest calls", "most powerful") that makes people watch to the end.
Avoid intros, sponsor reads, other channels' logos or on-screen text, and moments with loud copyrighted music.
Reply JSON only:
{{"titolo": "max 60 chars, curiosity title", "descrizione": "1 sentence", "hashtags": ["#...", "..."],
 "items": [{{"inizio": 0.0, "fine": 0.0, "perche": "what happens"}}]}}

MOMENTS:
{momenti}"""

VOCE = """You are the narrator of a viral Shorts countdown titled "{titolo}" (source: {canale}). Voice: {tono}.
For each of the 5 clips you get 3 frames and what is said in it. Write the narrator line spoken over the
first seconds of that clip, BEFORE the original audio plays:
- max 7 words, punchy, present tense, numbers and scale when you are sure of them;
- describe ONLY what is really visible in the frames / said in the transcript (no invented facts, no guessed species);
- start with the rank, e.g. "Number 5: ...".
Also write "gancio": max 7 words spoken at the very start to stop the scroll, coherent with the clips.
Then write the post texts. They MUST match what the frames show and what the narrator says (real footage only).
- "titolo": max 60 chars, curiosity-driven; "descrizione": 1 sentence; "hashtags": 5 relevant.
Reply JSON only: {{"gancio": "...", "voci": ["...", "...", "...", "...", "..."],
 "titolo": "...", "descrizione": "...", "hashtags": ["#...", "..."]}}

Transcripts:
{trascritti}"""


def _parole(tutte, a, b):
    return [(x - a, y - a, w) for x, y, w in tutte if a <= x < b]


def crea(url, src, momenti, tutte, chiave, lavoro, voce="en-US-GuyNeural", nicchia="viral videos",
         tono="documentary narrator", cta=""):
    """Ritorna (percorso video, testi per la didascalia)."""
    testo = []
    for i, m in enumerate(momenti):
        frasi = " ".join(f"[{a:.0f}] {w}" if k % 10 == 0 else w for k, (a, _, w) in enumerate(m["parole"]))
        testo.append(f"--- moment {i + 1} (starts {m['inizio']:.0f}) ---\n{frasi or '(loud, no speech)'}")
    s = scrittore.gemini(chiave, SCELTA.format(nicchia=nicchia, titolo=src["titolo"], canale=src["canale"],
                                               momenti="\n".join(testo)), 0.6)
    items = [it for it in s["items"] if 3 <= float(it["fine"]) - float(it["inizio"]) <= 12][:5]
    if len(items) < 3:
        raise RuntimeError("Top 5: troppo pochi momenti validi")
    pezzi, immagini, trascritti = [], [], []
    for n, it in enumerate(items):
        a, b = float(it["inizio"]), float(it["fine"]) + 3  # margine per la voce narrante
        raw = sorgenti.scarica_pezzo(url, a, b, os.path.join(lavoro, f"top{n}.mp4"))
        for k, f in enumerate((0.2, 0.5, 0.8)):
            jpg = os.path.join(lavoro, f"top{n}_{k}.jpg")
            editor.run(["ffmpeg", "-y", "-ss", f"{(b - a) * f:.1f}", "-i", raw, "-frames:v", "1",
                        "-vf", "scale=512:-2", jpg])
            immagini.append((f"Clip {n + 1}, frame {k + 1}:", jpg))
        trascritti.append(f"Clip {n + 1}: " + " ".join(w for *_, w in _parole(tutte, a, b)))
        pezzi.append((raw, a, b))
    v = scrittore.gemini(chiave, VOCE.format(titolo=s["titolo"], canale=src["canale"], tono=tono,
                                             trascritti="\n".join(trascritti)), 0.7, immagini)
    for k in ("titolo", "descrizione", "hashtags"):  # testi riscritti guardando le immagini
        if v.get(k):
            s[k] = v[k]
    voci = (v.get("voci") or [])[:len(pezzi)]
    if len(voci) < len(pezzi):
        raise RuntimeError("Top 5: voce narrante incompleta")
    segmenti = []
    for n, ((raw, a, b), frase) in enumerate(zip(pezzi, voci)):
        if n == 0 and v.get("gancio"):
            frase = v["gancio"] + " " + frase
        mp3 = os.path.join(lavoro, f"voce{n}.mp3")
        parole_voce = editor.voce_ai(frase, voce, mp3)
        d = editor.durata(mp3) + 0.2
        dur = min(max(float(items[n]["fine"]) - a, d + 3.5), b - a, 10)
        streamer = [(x + 0, y, w) for x, y, w in _parole(tutte, a, a + dur) if x >= d]
        gruppi = editor.gruppi_parole(parole_voce + streamer, frase, dur)
        ass = os.path.join(lavoro, f"top{n}.ass")
        editor.scrivi_ass(ass, gruppi, f"#{len(pezzi) - n}", dur, "Clip: " + src["canale"],
                          s["titolo"] if n == 0 else "", cta=cta if n == len(pezzi) - 1 else "")
        out = os.path.join(lavoro, f"seg_top{n}.mp4")
        fc = ("[0:v]split[x][y];[x]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
              "boxblur=25:3,eq=brightness=-0.2[bg];[y]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
              f"[bg][fg]overlay=(W-w)/2:'if(lt(h,1100),(H-h)/2-120,(H-h)/2)',fps=30,setsar=1,{editor.ass_filtro(ass)}[v];"
              f"[0:a]volume='if(lt(t,{d:.2f}),0.2,1)':eval=frame[o];[1:a]apad[n];"
              "[o][n]amix=inputs=2:duration=first:normalize=0,aresample=44100,"
              "aformat=sample_fmts=fltp:channel_layouts=stereo[a]")
        editor.run(["ffmpeg", "-y", "-i", raw, "-i", mp3, "-t", f"{dur:.2f}", "-filter_complex", fc,
                    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                    "-maxrate", "3M", "-bufsize", "6M", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "44100", out])
        segmenti.append(out)
    video = os.path.join(lavoro, "top5.mp4")
    editor.WORK = lavoro
    editor.unisci(segmenti, video)
    return video, {"titolo": s["titolo"], "descrizione": s.get("descrizione", ""),
                   "hashtags": s.get("hashtags") or ["#shorts"]}
