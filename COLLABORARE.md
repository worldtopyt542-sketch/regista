# Come collaboriamo su Autoclipping-video virali di massa (2 persone + Claude Code)

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

## Come si chiede un lavoro a Claude
Apri Claude Code nel repo e scrivi, per esempio:
> Leggi COLLABORARE.md e l'Issue #N. Crea il branch, fai il lavoro, apri la Pull Request.

## Dove si vede tutto
- **Issues**: lista delle cose da fare (una per idea/problema).
- **Pull requests**: lavori pronti da controllare.
- **Actions**: i giri automatici (verde = ok, rosso = errore da guardare).
- **Telegram**: i video da approvare arrivano solo al proprietario del bot.
