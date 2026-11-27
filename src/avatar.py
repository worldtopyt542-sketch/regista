# ==== AVATAR PER LINGUA: stessa matrice del brand, con l'etichetta della lingua ====
# Una pagina per lingua su TikTok/Instagram/YouTube, tutte riconoscibili come Planet Off Scale.
#   python src/avatar.py   -> assets/avatar_<lingua>.png (1080x1080) per ogni lingua attiva e futura
import os, sys
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(__file__))
import comune


def crea(cod, dest):
    b = comune.brand()
    img = Image.open(os.path.join(comune.RADICE, "assets", "avatar.png")).convert("RGB")
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(os.path.join(comune.RADICE, "assets", "fonts", "InterDisplay-Black.otf"), 120)
    testo = cod.upper()
    l, t, r, bt = d.textbbox((0, 0), testo, font=font)
    w, h = r - l, bt - t
    x, y = (1080 - w) // 2, 55  # in alto al centro: resta dentro il ritaglio rotondo dei profili
    d.rounded_rectangle((x - 40, y - 25, x + w + 40, y + h + 45), radius=40, fill=b["colore"])
    d.text((x - l, y - t + 10), testo, font=font, fill="#0b0b1e")
    img.save(dest, optimize=True)
    return dest


def main():
    cfg = comune.carica(comune.CONFIG, {})
    codici = sys.argv[1:] or list(comune.lingue(cfg))  # es. python src/avatar.py hi pt
    for cod in codici:
        print("->", crea(cod, os.path.join(comune.RADICE, "assets", f"avatar_{cod}.png")))


if __name__ == "__main__":
    main()
