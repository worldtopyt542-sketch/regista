# ==== ANTEPRIMA DEL FORMAT, in locale e senza chiavi ====
# Monta una clip finta (o un tuo video) con il brand kit attuale, in tutte le lingue, e salva un PNG per lingua.
# Serve a ritoccare grafica/brand dal proprio PC senza aspettare il giro notturno su GitHub Actions.
#   python src/anteprima.py                      -> sorgente sintetica, output in anteprima/
#   python src/anteprima.py mio_video.mp4 12     -> 12 s del tuo video
import os, subprocess, sys

sys.path.insert(0, os.path.dirname(__file__))
import comune, editor
from clipper import monta

TESTI = {
    "en": ("THIS STAR IS OFF SCALE", ["THIS", "STAR", "COULD", "SWALLOW", "OUR", "WHOLE", "SOLAR", "SYSTEM"]),
    "it": ("QUESTA STELLA E' FUORI SCALA", ["QUESTA STELLA POTREBBE INGOIARE", "IL NOSTRO SISTEMA SOLARE"]),
    "es": ("ESTA ESTRELLA ES DESCOMUNAL", ["ESTA ESTRELLA PODRÍA TRAGARSE", "TODO NUESTRO SISTEMA SOLAR"]),
}


def sorgente(dest, dur):
    """Video 16:9 sintetico (frattale animato + tono) per provare il template senza scaricare niente."""
    editor.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"mandelbrot=s=1280x720:rate=30,format=yuv420p",
                "-f", "lavfi", "-i", f"sine=frequency=220:sample_rate=44100", "-t", str(dur),
                "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", dest])
    return dest


def main():
    out_dir = os.path.join(comune.RADICE, "anteprima")
    os.makedirs(out_dir, exist_ok=True)
    editor.WORK = out_dir
    dur = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
    src = sys.argv[1] if len(sys.argv) > 1 else sorgente(os.path.join(out_dir, "sorgente.mp4"), dur)
    cfg = comune.carica(comune.CONFIG, {})
    for cod, lg in comune.lingue(cfg).items():
        hook, parole = TESTI.get(cod, TESTI["en"])
        passo = (dur - 0.5) / len(parole)
        if cod == "en":  # karaoke parola per parola
            gruppi = editor.gruppi_parole([(i * passo, (i + 1) * passo, w) for i, w in enumerate(parole)], "", dur)
        else:  # frase intera
            gruppi = [[(i * passo, (i + 1) * passo, f)] for i, f in enumerate(parole)]
        out = os.path.join(out_dir, f"anteprima_{cod}.mp4")
        monta(src, dur, gruppi, hook, "Clip: NASA Goddard (CC BY)", out, out_dir, lg.get("font"),
              84 if cod == "en" else 64, comune.cta(cod, cfg))
        print("Critic:", "OK" if editor.critic(out, max_sec=60) else "da correggere")
        for nome, t in (("inizio", 1.0), ("fine", dur - 1.0)):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", out, "-frames:v", "1",
                            "-vf", "scale=540:-2", os.path.join(out_dir, f"anteprima_{cod}_{nome}.png")], check=True)
        print("->", out)


if __name__ == "__main__":
    main()
