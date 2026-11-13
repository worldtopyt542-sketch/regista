# Regista — Planet Off Scale

Ogni mattina alle 06:15 crea 3 short (Top 5, 25–30 s) e te li manda su Telegram con titolo, descrizione e fonti dei fatti da controllare. Tu li guardi e li programmi su Buffer.

Agent: Sceneggiatore (Gemini) → Scout (Pixabay, NASA, Pexels se disponibile) → Voce (Edge TTS) → Editor → Critic → Telegram.
`archivio.json` ricorda titoli e clip già usati, così i video non si ripetono.

## Secrets da inserire (Settings → Secrets and variables → Actions → New repository secret)

| Nome | Da dove arriva |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Il token che ti ha dato @BotFather |
| `GEMINI_API_KEY` | https://aistudio.google.com → Get API key |
| `PIXABAY_API_KEY` | https://pixabay.com/api/docs/ (la chiave compare nella pagina dopo il login) |
| `PEXELS_API_KEY` | Facoltativa: Pexels ha sospeso le nuove chiavi |

Non scrivere mai queste chiavi nei file o in chat.

## Avviarlo a mano
Scheda **Actions** → **Regista - video del giorno** → **Run workflow**.

## Cambiare temi, voce o numero di video
Modifica `config.json` direttamente da GitHub (icona matita).
