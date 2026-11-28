# ==== EDITOR + CRITIC + VOCE (collaudati sul notebook Colab) ====
import asyncio, json, os, re, shutil, subprocess, urllib.parse, urllib.request

W, H, FPS = 1080, 1920, 30
WORK = "lavoro"
SKIP_WORDS = ("©", "copyright", "courtesy of", "used with permission", "all rights reserved")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("Errore ffmpeg:\n" + r.stderr[-1500:])
    return r.stdout


def durata(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", path])
    return float(out.strip())


# ---------- Voce AI (Edge TTS) con tempi delle parole ----------
async def _tts(testo, voce, mp3):
    import edge_tts
    try:
        com = edge_tts.Communicate(testo, voce, boundary="WordBoundary")
    except TypeError:
        com = edge_tts.Communicate(testo, voce)
    parole = []
    with open(mp3, "wb") as f:
        async for c in com.stream():
            if c["type"] == "audio":
                f.write(c["data"])
            elif c["type"] == "WordBoundary":
                parole.append((c["offset"] / 1e7, (c["offset"] + c["duration"]) / 1e7, c["text"]))
    return parole


def voce_ai(testo, voce, mp3):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():  # Colab ha gia' un loop attivo
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(_tts(testo, voce, mp3))
    return asyncio.run(_tts(testo, voce, mp3))


# ---------- Agent EDITOR: sottotitoli + montaggio 9:16 ----------
def t_ass(s):
    cs = int(round(s * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def gruppi_parole(parole, testo, dur, n=3):
    if not parole:  # nessun tempo dalla voce: divido il testo in modo uniforme
        w = testo.split()
        passo = dur / max(1, len(w))
        parole = [(i * passo, (i + 1) * passo, x) for i, x in enumerate(w)]
    # gruppi di 3 parole; ogni parola resta visibile fino all'inizio della successiva
    tempi = [(a, parole[k + 1][0] if k + 1 < len(parole) else dur, w)
             for k, (a, b, w) in enumerate(parole)]
    return [tempi[i:i + n] for i in range(0, len(tempi), n)]


FONT = "Inter Display Black"  # font del marchio (assets/fonts, licenza OFL)
ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


def ass_filtro(path):
    return f"ass={path}:fontsdir={os.path.join(ASSETS, 'fonts')}"


def _brand():
    import comune
    return comune.brand()


def ass_colore(hexrgb, alpha="00"):
    """'#FFD400' -> '&H0000D4FF' (ASS vuole alpha+BGR)."""
    h = hexrgb.lstrip("#")
    return f"&H{alpha}{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def logo_path():
    return os.path.join(os.path.dirname(ASSETS), _brand()["logo_video"])


def filtro_marchio(d, ingresso, logo, uscita, y_logo=548):
    """Pezzo di filtergraph: logo 'bug' + barra di avanzamento nel colore del brand (Y della barra: 1150)."""
    col = "0x" + _brand()["colore"].lstrip("#")
    return (f"{logo}scale=260:-1,format=rgba,colorchannelmixer=aa=0.9[logo];"
            f"{ingresso}drawbox=x=0:y=1150:w=1080:h=14:color=white@0.25:t=fill[mb];"
            f"color=c={col}:s=1080x14:d={d:.2f}[bar];"
            f"[mb][bar]overlay=x='-w+w*t/{d:.2f}':y=1150:shortest=1[mc];"
            f"[mc][logo]overlay=x=24:y={y_logo}{uscita}")


def marchia(video, out):
    """Format riconoscibile su ogni video: logo 'bug' + barra di avanzamento (usato da Top 5 e Facts)."""
    d = durata(video)
    fc = filtro_marchio(d, "[0:v]", "[1:v]", "[v]")
    run(["ffmpeg", "-y", "-i", video, "-i", logo_path(), "-filter_complex", fc,
         "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-maxrate", "3M",
         "-bufsize", "6M", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", out])
    return out


def scrivi_ass(path, gruppi, etichetta, dur, credito, hook="", font=None, cap=84, cta="", testata=""):
    b = _brand()
    font = font or b.get("font") or FONT
    acc = ass_colore(b["colore"])
    pulisci = lambda s: s.replace("{", "(").replace("}", ")").replace("\n", " ")
    righe = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        # zone sicure: niente testo nel 10% alto, 15% basso, 12% destro (pulsanti di YouTube)
        f"Style: Cap,{font},{cap},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,7,3,2,60,150,540,1",
        f"Style: Rank,{font},190,{acc},&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,9,4,8,60,150,330,1",
        f"Style: Hook,{font},70,&H00000000,&H000000FF,{acc},&H00000000,-1,0,0,0,100,100,0,0,3,18,0,8,80,170,200,1",
        f"Style: Cred,{font},34,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,60,150,310,1",
        # testata fissa per tutto il video (come gli Shorts di riferimento): chi scorre senza audio capisce subito
        f"Style: Testa,{font},54,&H00FFFFFF,&H000000FF,&H40000000,&H00000000,-1,0,0,0,100,100,0,0,3,16,0,8,90,180,215,1",
        f"Style: Cta,{font},54,&H00000000,&H000000FF,{acc},&H00000000,-1,0,0,0,100,100,0,0,3,14,0,2,80,170,400,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    if testata:
        righe.append(f"Dialogue: 0,{t_ass(0)},{t_ass(dur)},Testa,,0,0,0,,{pulisci(testata).upper()}")
    if etichetta:  # "#3 BOOTES VOID": numero grande, nome sotto piu' piccolo e bianco
        num, _, nome = pulisci(etichetta).partition(" ")
        nome = ("\\N{\\fs72\\c&H00FFFFFF&}" + nome.upper()) if nome else ""
        righe.append(f"Dialogue: 0,{t_ass(0)},{t_ass(dur)},Rank,,0,0,{410 if testata else 330},,{num}{nome}")
    if hook:  # titolo-gancio in un box nero per i primi 3 secondi
        righe.append(f"Dialogue: 0,{t_ass(0)},{t_ass(min(3, dur))},Hook,,0,0,0,,{pulisci(hook).upper()}")
    giallo, bianco = "{\\c" + acc + "&}", r"{\c&H00FFFFFF&}"
    for g in gruppi:  # la parola pronunciata diventa gialla (#FFD400)
        for i, (a, b, _) in enumerate(g):
            txt = " ".join((giallo + pulisci(w).upper() + bianco) if j == i else pulisci(w).upper()
                           for j, (_, _, w) in enumerate(g))
            righe.append(f"Dialogue: 0,{t_ass(a)},{t_ass(b)},Cap,,0,0,0,,{txt}")
    righe.append(f"Dialogue: 0,{t_ass(0)},{t_ass(dur)},Cred,,0,0,0,,{pulisci(credito)}")
    if cta and dur > 6:  # invito a seguire negli ultimi 2.5 s, con dissolvenza
        righe.append(f"Dialogue: 1,{t_ass(dur - 2.5)},{t_ass(dur)},Cta,,0,0,0,,{{\\fad(250,0)}}{pulisci(cta).upper()}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(righe) + "\n")


def monta_segmento(clip, audio, parole, testo, etichetta, credito, out, n, hook="", font=None, cta="",
                   testata="", stacco=False):
    """stacco=True: lampo bianco + whoosh all'inizio del segmento (cambio scena dei format di riferimento)."""
    dur = durata(audio) + 0.25
    ass = os.path.join(WORK, f"seg{n}.ass")
    scrivi_ass(ass, gruppi_parole(parole, testo, dur), etichetta, dur, credito, hook, font, cta=cta, testata=testata)
    z = f"(1+0.08*t/{dur:.2f})"  # zoom lento da 1.00 a 1.08
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"scale=w='trunc({W}*{z}/2)*2':h='trunc({H}*{z}/2)*2':eval=frame,crop={W}:{H},"
          f"fps={FPS},setsar=1,{'fade=t=in:st=0:d=0.18:color=white,' if stacco else ''}{ass_filtro(ass)}")
    if stacco:  # whoosh sintetico (rumore rosa filtrato): nessun file audio di terzi
        af = ["-filter_complex", "anoisesrc=d=0.6:c=pink:a=0.6,highpass=f=500,lowpass=f=6000,"
              "afade=t=in:d=0.08,afade=t=out:st=0.12:d=0.45,volume=0.35[w];[1:a]apad[v];"
              "[v][w]amix=inputs=2:duration=first:normalize=0[a]", "-map", "0:v:0", "-map", "[a]"]
    else:
        af = ["-af", "apad", "-map", "0:v:0", "-map", "1:a:0"]
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", clip, "-i", audio,
         "-t", f"{dur:.2f}", "-vf", vf, *af,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-ar", "44100", "-ac", "2", out])


def tappeto(dur, out):
    """Tappeto 'dark ambient' generato da ffmpeg (due sinusoidi basse + rumore scuro): libero da diritti."""
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=f=55:d={dur:.1f}", "-f", "lavfi", "-i", f"sine=f=82.4:d={dur:.1f}",
         "-f", "lavfi", "-i", f"anoisesrc=d={dur:.1f}:c=brown:a=0.4",
         "-filter_complex", "[0:a][1:a][2:a]amix=inputs=3:normalize=0,lowpass=f=420,tremolo=f=0.15:d=0.5,"
         f"afade=t=in:d=1.5,afade=t=out:st={max(0, dur - 2):.1f}:d=2,volume=0.22",
         "-ac", "2", "-ar", "44100", out])
    return out


def unisci(segmenti, out, musica=False):
    lista = os.path.join(WORK, "lista.txt")
    with open(lista, "w") as f:
        for s in segmenti:
            f.write(f"file '{os.path.abspath(s)}'\n")
    tmp = os.path.join(WORK, "unito.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", tmp])
    if musica:  # la voce resta sopra: il tappeto sta circa 18 dB sotto
        letto = tappeto(durata(tmp), os.path.join(WORK, "tappeto.wav"))
        con = os.path.join(WORK, "unito_musica.mp4")
        run(["ffmpeg", "-y", "-i", tmp, "-i", letto, "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:normalize=0[a]",
             "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-ar", "44100", con])
        tmp = con
    # volume standard dei social: -14 LUFS
    run(["ffmpeg", "-y", "-i", tmp, "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
         "-c:a", "aac", "-ar", "44100", "-b:a", "192k", "-movflags", "+faststart", out])


def lufs(video):
    r = subprocess.run(["ffmpeg", "-i", video, "-af", "loudnorm=I=-14:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r'"input_i"\s*:\s*"(-?[\d.]+)"', r.stderr)
    return float(m.group(1)) if m else None


# ---------- Agent CRITIC: controlli automatici ----------
def critic(video, max_sec=60):
    info = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format",
                           "-of", "json", video]))
    v = [s for s in info["streams"] if s["codec_type"] == "video"]
    a = [s for s in info["streams"] if s["codec_type"] == "audio"]
    dur = float(info["format"]["duration"])
    problemi = []
    if not v or (int(v[0]["width"]), int(v[0]["height"])) != (W, H):
        problemi.append("formato diverso da 1080x1920 (9:16)")
    if not a:
        problemi.append("manca l'audio")
    if dur > max_sec:
        problemi.append(f"durata {dur:.0f}s, oltre {max_sec}s")
    vol = lufs(video)
    if vol is None or not (-16 <= vol <= -12):
        problemi.append(f"volume {vol} LUFS invece di circa -14")
    print(f"Critic: durata {dur:.1f}s, volume {vol} LUFS")
    if problemi:
        print("Critic: DA CORREGGERE ->", "; ".join(problemi))
    else:
        print("Critic: OK (formato 9:16, audio presente, durata giusta)")
    return not problemi
