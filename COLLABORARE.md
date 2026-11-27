# Come collaboriamo su Regista (2 persone + Claude Code)

## Chi fa cosa
- **Il lavoro pesante** (scaricare, trascrivere, montare, pubblicare) gira su **GitHub Actions**, non sui nostri PC.
- **Claude Code** (uno per ciascuno, ognuno col suo Claude Pro) serve a **sviluppare**: nuove funzioni, correzioni, nuovi format.
- Le regole per Claude sono in `CLAUDE.md`: entrambi i Claude le leggono da soli.

## Regole d'oro
1. **Mai lavorare direttamente su `main`**: `main` è quello che gira ogni notte.
2. Ogni lavoro = un **branch** `nome/cosa` (es. `marco/nuovo-format`) + una **Pull Request** verso `main`.
3. L'altro **approva la PR** (basta un'occhiata + il commento di Claude) prima del merge.
4. Prima di iniziare: `git pull` su `main` e scrivi nell'**Issue** su cosa lavori, così non ci pestiamo i piedi.
5. **Non toccare a mano** `archivio.json`, `clipper.json`, `pubblica.json`: li scrive il bot.
6. **Mai chiavi nei file o in chat**: stanno solo in Settings → Secrets (le usa GitHub, non servono a noi).

## Come ci dividiamo il lavoro (PC diversi)
Il lavoro pesante gira comunque su GitHub Actions. Sui PC gira solo lo sviluppo, quindi:
- **Fra (PC piu' potente)**: grafica e format (`python src/anteprima.py` in loop, render di prova con video veri,
  Whisper in locale), format nuovi, agent `format-designer` e `nuovo-canale`.
- **Proprietario del repo (PC piu' leggero)**: niente render in locale. Config e contenuti (`config.json`: ricerche,
  temi, lingue, orari), approvazioni su Telegram, canali Buffer/TikTok/Instagram/YouTube per lingua, revisione delle
  PR con l'agent `revisore-pr` e il link all'anteprima negli artifact del workflow "Controlli (PR)".
- Chi vuole vedere un render senza farlo sul proprio PC: Actions → **Controlli (PR)** → artifact `anteprima-format`.

## L'Autoclipper sul PC di Fra (YouTube blocca GitHub)
YouTube spesso rifiuta i download dai server di GitHub. Soluzione: il PC di Fra fa da "runner" per il solo Autoclipper.
1. GitHub → Settings → Actions → Runners → **New self-hosted runner** (macOS), e si seguono i 3 comandi; poi `./svc.sh install && ./svc.sh start`
   (serve un admin del repo).
2. Sul Mac: `brew install ffmpeg yt-dlp` (Python 3.12 c'e' gia' o `brew install python@3.12`).
3. Settings → Secrets and variables → Actions → **Variables** → `CLIPPER_RUNNER` = `self-hosted`.
Togliendo la variabile si torna ai server di GitHub. In alternativa: secret `YT_COOKIES` (cookie di un account YouTube secondario).

## Lo stato del bot sta nel ramo `stato`
`main` e' protetto (solo Pull Request), quindi `archivio.json`, `clipper.json`, `pubblica.json` e `pronte/` li scrive il bot
nel ramo **`stato`** (`.github/carica-stato.sh` e `.github/salva-stato.sh`). Le copie su `main` sono solo il punto di partenza.

## Agent pronti per Claude Code (`.claude/agents/`)
- `format-designer`: "migliora la grafica del format", "nuovo format Scale Check".
- `revisore-pr`: "rivedi la PR #N" (licenze, chiavi, file di stato, bug).
- `nuovo-canale`: "aggiungi la lingua portoghese", "replica per un canale di oceani".

## Come si chiede un lavoro a Claude
Apri Claude Code nel repo e scrivi, per esempio:
> Leggi COLLABORARE.md e l'Issue #N. Crea il branch, fai il lavoro, apri la Pull Request.

## Dove si vede tutto
- **Issues**: lista delle cose da fare (una per idea/problema).
- **Pull requests**: lavori pronti da controllare.
- **Actions**: i giri automatici (verde = ok, rosso = errore da guardare).
- **Telegram**: i video da approvare arrivano solo al proprietario del bot.
