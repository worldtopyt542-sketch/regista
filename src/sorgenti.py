# ==== AGENT SORGENTI: raccoglie i video lunghi da clippare ====
# 1) link mandati al bot Telegram  2) nuovi video dai canali in config.json  3) URL passato a mano
import json, os, re, subprocess
import requests

URL_RE = re.compile(r"https?://\S+")


def _yt(args):
    cmd = ["yt-dlp", "--no-warnings", "--no-playlist"]
    if os.path.exists("cookies.txt"):
        cmd += ["--cookies", "cookies.txt"]
    r = subprocess.run(cmd + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("yt-dlp: " + r.stderr.strip()[-400:])
    return r.stdout


def da_telegram(token, chat_id, arch):
    """Link inviati al bot dopo l'ultimo controllo."""
    r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates",
                     params={"offset": arch.get("ultimo_update", 0) + 1}, timeout=60).json()
    link = []
    for u in r.get("result", []):
        arch["ultimo_update"] = u["update_id"]
        m = u.get("message") or {}
        if (m.get("chat") or {}).get("id") == chat_id:
            link += URL_RE.findall(m.get("text") or m.get("caption") or "")
    return link


def da_canali(canali, parole, fatti, quanti=2):
    """Ultimi video dei canali in lista che parlano del tema (es. 'gta')."""
    out = []
    for c in canali:
        presi = 0
        try:
            righe = _yt(["--flat-playlist", "--playlist-end", "8", "--print", "%(url)s\t%(title)s",
                         "--yes-playlist", c]).splitlines()
        except RuntimeError as e:
            print(f"   Sorgenti: {c} saltato ({e})")
            continue
        for r in righe:
            url, _, titolo = r.partition("\t")
            if url not in fatti and any(p in titolo.lower() for p in parole):
                out.append(url)
                presi += 1
                if presi >= quanti:
                    break
    return out


def info(url):
    j = json.loads(_yt(["-J", url]))
    return {"id": j.get("extractor_key", "") + ":" + str(j.get("id")), "titolo": j.get("title", ""),
            "canale": j.get("uploader") or j.get("channel") or "", "durata": j.get("duration") or 0}


def scarica_audio(url, dest):
    _yt(["-f", "ba/b", "-x", "--audio-format", "wav", "--postprocessor-args", "ExtractAudio:-ac 1 -ar 16000",
         "-o", dest + ".%(ext)s", url])
    return dest + ".wav"


def scarica_pezzo(url, inizio, fine, dest):
    _yt(["-f", "bv*[height<=1080]+ba/b[height<=1080]", "--download-sections", f"*{inizio:.1f}-{fine:.1f}",
         "--force-keyframes-at-cuts", "--merge-output-format", "mp4", "-o", dest, url])
    return dest
