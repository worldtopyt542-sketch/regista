# Autoclipping-video virali di massa

Sistema automatico che ogni notte trova video virali **senza copyright** (Creative Commons BY con almeno 1M di views,
o pubblico dominio), ne estrae le clip migliori, monta Short verticali col format del canale **Planet Off Scale**
e te li manda su Telegram. Tu premi ✅ e vengono pubblicati da soli su TikTok, Instagram e YouTube Shorts.

## Come gira
| Workflow | Quando | Cosa fa |
|---|---|---|
| Autoclipper Planet Off Scale | ogni notte | 8 clip + 2 Top 5 su Telegram |
| Pubblicatore | ogni 15 min | ✅ → pubblica via Buffer nell'orario migliore, report serale |

## Secret (Settings → Secrets and variables → Actions)
`TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `BUFFER_API_KEY`, `YOUTUBE_API_KEY`, `YT_COOKIES` (se YouTube blocca i download).
Mai scrivere chiavi nei file o in chat.

## Lavorare in due
Vedi `COLLABORARE.md`.
