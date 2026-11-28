# ==== COPERTURA: la scaletta ha filmati veri e di qualita' per ogni voce? ====
# Per ogni voce cerca video NASA, foto NASA (pubblico dominio) e, se servono, Pexels verticali 4K. Nessun download.
# Nel log: (video NASA / foto NASA / Pexels 4K) per ogni voce debole.
# Uso: python src/copertura.py   -> tabella nel log + copertura.json (artefatto del workflow)
import json, os, re, sys, time, urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
from comune import RADICE, carica, salva
from fonti import SOSPETTI, _get_json

PEXELS_MAX = 150  # Pexels concede 200 richieste l'ora


def query(voce):
    """'first spacewalk 1965' -> 'first spacewalk': via anni, numeri e parole vuote."""
    q = re.sub(r"\b\d[\d,.]*\b|\b(the|a|an|of|on|in|to|its|it|from|with)\b", " ", voce, flags=re.I)
    return " ".join(q.split()[:4]) or voce


def nasa(q, tipo="video"):
    url = "https://images-api.nasa.gov/search?" + urllib.parse.urlencode({"q": q, "media_type": tipo})
    items = _get_json(url).get("collection", {}).get("items", [])
    buoni = []
    for it in items:
        d = it["data"][0]
        testo = " ".join(str(d.get(k, "")) for k in ("title", "description", "secondary_creator")).lower()
        if not any(p in testo for p in SOSPETTI):
            buoni.append(d.get("title", "")[:70])
    return buoni


def pexels(q, chiave):
    url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
        {"query": q, "orientation": "portrait", "size": "large", "per_page": 15})
    dati = _get_json(url, {"Authorization": chiave})
    return [v.get("url", "") for v in dati.get("videos", [])
            if any((f.get("height") or 0) >= 1920 for f in v.get("video_files", []))]


def main():
    chiave = (os.environ.get("PEXELS_API_KEY") or "").strip()
    voci = carica(os.path.join(RADICE, "scaletta.json"), {}).get("video") or []
    usate_pexels, report = 0, []
    for v in voci:
        righe = []
        for s in v["voci"]:
            q = query(s)
            try:
                n = nasa(q)
            except Exception as e:
                n = []
                print("   nasa errore:", e)
            try:
                fo = nasa(q, "image") if len(n) < 3 else []
            except Exception:
                fo = []
            p = []
            if len(n) < 3 and len(fo) < 3 and chiave and usate_pexels < PEXELS_MAX:
                try:
                    p = pexels(q, chiave)
                except Exception as e:
                    print("   pexels errore:", e)
                usate_pexels += 1
            righe.append({"voce": s, "query": q, "nasa": len(n), "foto_nasa": len(fo), "pexels_4k": len(p),
                          "esempio": (n or fo or p or [""])[0], "ok": len(n) >= 3 or len(fo) >= 3 or len(p) >= 2})
            time.sleep(0.3)
        ok = sum(r["ok"] for r in righe)
        report.append({"n": v["n"], "titolo": v["titolo"], "voci_ok": ok, "dettaglio": righe})
        deboli = ", ".join(f"{r['voce']} ({r['nasa']}/{r['foto_nasa']}/{r['pexels_4k']})" for r in righe if not r["ok"])
        print(f"#{v['n']:>3} {ok}/5 {v['titolo']}" + (f"  -> deboli: {deboli}" if deboli else ""), flush=True)
    salva(os.path.join(RADICE, "copertura", "copertura.json"), report)
    deboli = [r for r in report if r["voci_ok"] < 4]
    print(f"\nVideo con meno di 4 voci coperte: {len(deboli)} su {len(report)}")
    for r in deboli:
        print(f"  #{r['n']} {r['titolo']} ({r['voci_ok']}/5)")


if __name__ == "__main__":
    main()
