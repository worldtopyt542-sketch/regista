# ==== AGENT SORGENTI: scarica info, audio e pezzi dei video lunghi (yt-dlp) ====
import json, os, subprocess


def _yt(args):
    cmd = ["yt-dlp", "--no-warnings", "--no-playlist"]
    if os.path.exists("cookies.txt"):
        cmd += ["--cookies", "cookies.txt"]
    r = subprocess.run(cmd + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("yt-dlp: " + r.stderr.strip()[-400:])
    return r.stdout


def info(url):
    j = json.loads(_yt(["-J", url]))
    return {"id": j.get("extractor_key", "") + ":" + str(j.get("id")), "titolo": j.get("title", ""),
            "canale": j.get("uploader") or j.get("channel") or "", "durata": j.get("duration") or 0}


def scarica_audio(url, dest, inizio, fine):
    """Solo l'audio del blocco [inizio, fine] in secondi (niente WAV giganti)."""
    import glob
    _yt(["-f", "ba/b", "--download-sections", f"*{inizio:.0f}-{fine:.0f}", "-o", dest + ".%(ext)s", url])
    return sorted(glob.glob(dest + ".*"))[0]


def scarica_pezzo(url, inizio, fine, dest):
    _yt(["-f", "bv*[height<=1080]+ba/b[height<=1080]", "--download-sections", f"*{inizio:.1f}-{fine:.1f}",
         "--force-keyframes-at-cuts", "--merge-output-format", "mp4", "-o", dest, url])
    return dest
