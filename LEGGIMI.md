# Regista — Planet Off Scale

Fabbrica automatica di Shorts / Reels / TikTok in piu' lingue, tutti nello stesso format (vedi [FORMAT.md](FORMAT.md)).

Ogni notte: **Autoclipper** (clip + Top 5 da video YouTube CC BY) e **Off Scale Facts** (fatti veri con filmati NASA).
Ogni video arriva su Telegram con tutte le lingue: un ✅ le mette in programma tutte, ognuna negli orari migliori del
suo pubblico e sui suoi canali. Il **Pubblicatore** (ogni 15 min) pubblica via Buffer e alle 21 manda il report.

## Secrets (Settings → Secrets and variables → Actions)
| Nome | Da dove arriva |
|---|---|
| `TELEGRAM_BOT_TOKEN` | @BotFather |
| `GEMINI_API_KEY` | https://aistudio.google.com → Get API key |
| `YOUTUBE_API_KEY` | Google Cloud → YouTube Data API v3 (ricerca e verifica licenze) |
| `BUFFER_API_KEY` | Buffer → impostazioni API |
| `PIXABAY_API_KEY` | https://pixabay.com/api/docs/ (Facts) |
| `PEXELS_API_KEY` | facoltativa |
| `YT_COOKIES` | facoltativo, se YouTube blocca i download dai server di GitHub |

## Avviare a mano
Scheda **Actions** → "Autoclipper Planet Off Scale" o "Off Scale Facts" → **Run workflow**.

## Aggiungere una lingua o un canale
`config.json` (lingue, `brand.cta`, `pubblica.canali`) e `python src/avatar.py <lingua>`. Dettagli: agent `nuovo-canale`.
