# ==== RIFERIMENTI: Gemini guarda gli Shorts presi a modello e ne ricava la "ricetta" del format ====
# Non scarica niente da YouTube (bloccato sui server GitHub): Gemini legge il link pubblico da solo.
# Uso: python src/riferimenti.py URL [URL ...]   -> riferimenti/<id>.json + sintesi stampata nel log
import json, os, re, sys, time, urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
import scrittore
from comune import RADICE, salva

ANALISI = """You are a short-form video editor. Watch this YouTube Short carefully, second by second, and reverse-engineer
its format so another team can replicate the STRUCTURE (not the content) with licensed footage (NASA, Pixabay, CC BY).
Return ONLY JSON:
{"titolo": "...", "durata_s": 0, "nicchia": "...",
 "hook": {"secondi": "0-2", "visivo": "...", "testo_a_schermo": "...", "voce": "...", "perche_ferma_lo_scroll": "..."},
 "battute": [{"da": 0, "a": 0, "cosa_succede": "...", "testo_a_schermo": "...", "voce": "..."}],
 "ritmo": {"tagli_totali": 0, "durata_media_inquadratura_s": 0, "zoom_o_movimenti": "..."},
 "testi": {"posizione": "...", "font": "...", "colori": "...", "dimensione": "...", "parola_per_parola": true,
           "emoji": false, "contorno_ombra": "...", "altro": "..."},
 "voce": {"tipo": "umana | AI TTS | nessuna", "tono": "...", "parole_al_minuto": 0, "lingua": "..."},
 "audio": {"musica": "...", "effetti_sonori": "...", "volume_relativo": "..."},
 "grafica": {"logo_watermark": "...", "barre_progresso": "...", "cornici_o_overlay": "...", "numeri_contatori": "..."},
 "finale": {"come_finisce": "...", "loop": false, "cta": "..."},
 "perche_funziona": ["...", "..."],
 "da_copiare": ["concrete, replicable rule 1", "..."],
 "da_evitare": ["..."]}"""

SINTESI = """These are analyses of {n} reference YouTube Shorts a creator wants to imitate. Merge them into ONE replicable
format recipe for a channel that only uses licensed footage (NASA public domain, Pixabay, CC BY YouTube), AI voice
(edge-tts) and ffmpeg/ASS captions. Be concrete and numeric (seconds, words per minute, font size in px on 1080x1920).
Return ONLY JSON:
{"nome_format": "...", "durata_s": 0, "struttura": [{"da": 0, "a": 0, "ruolo": "hook | fatto | twist | payoff | loop",
 "regola": "..."}], "hook": ["..."], "ritmo": {"durata_inquadratura_s": 0, "zoom": "..."},
 "testi": {"posizione_y_px": 0, "font": "...", "dimensione_px": 0, "colori": "...", "parola_per_parola": true,
 "parole_per_schermata": 0, "contorno": "..."}, "voce": {"tono": "...", "parole_al_minuto": 0},
 "audio": {"musica": "...", "sfx": "..."}, "finale": "...", "elementi_comuni": ["..."],
 "differenze_dal_nostro_format": ["..."], "modifiche_al_codice": ["..."]}
Analyses:
{dati}"""


def id_youtube(url):  # come scopri.id_youtube, senza dipendere da requests: il workflow installa solo Python
    m = re.search(r"(?:v=|youtu\.be/|shorts/|live/)([\w-]{11})", url or "")
    return m.group(1) if m else None


def gemini_video(chiave, url, prompt):
    body = {"contents": [{"parts": [{"file_data": {"file_uri": url, "mime_type": "video/*"}}, {"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}}
    errori = []
    for giro in range(4):
        for m in scrittore.modelli_candidati(chiave, scrittore.ULTIMO_BUONO):
            try:
                r = scrittore._post(f"{scrittore.BASE}models/{m}:generateContent?key={urllib.parse.quote(chiave)}", body)
                testo = "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"])
                scrittore.ULTIMO_BUONO = m
                return scrittore.estrai_json(testo), m
            except Exception as e:
                errori.append(f"{m}: {str(e)[:120]}")
        print(f"   Gemini occupato, attendo {60 * (giro + 1)} s")
        time.sleep(60 * (giro + 1))
    raise RuntimeError(" | ".join(errori[-4:]))


def main(urls):
    chiave = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not chiave:
        sys.exit("Manca il secret GEMINI_API_KEY")
    analisi = []
    for u in urls:
        vid = id_youtube(u)
        if not vid:
            print(f"Link non YouTube, salto: {u}")
            continue
        link = f"https://www.youtube.com/watch?v={vid}"
        print(f"=== Analizzo {link}")
        try:
            a, m = gemini_video(chiave, link, ANALISI)
        except Exception as e:
            print(f"   fallito: {e}")
            continue
        a["url"], a["modello"] = link, m
        salva(os.path.join(RADICE, "riferimenti", vid + ".json"), a)
        print(json.dumps(a, ensure_ascii=False, indent=1))
        analisi.append(a)
    if len(analisi) > 1:
        print("=== Sintesi")
        s = scrittore.gemini(chiave, SINTESI.replace("{n}", str(len(analisi)))
                             .replace("{dati}", json.dumps(analisi, ensure_ascii=False)), temp=0.3)
        salva(os.path.join(RADICE, "riferimenti", "sintesi.json"), s)
        print(json.dumps(s, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main([u for a in sys.argv[1:] for u in re.split(r"[\s,]+", a) if u])
