#!/usr/bin/env bash
# Salva i file di stato del bot. Prima era "git push || true": un push fallito perdeva lo stato in silenzio
# (e al giro dopo tornavano i doppioni). Ora riprova 4 volte e, se non ce la fa, il workflow diventa rosso.
# Uso: .github/salva-stato.sh "messaggio" file1 [file2 ...]
set -u
msg="$1"; shift
git config user.name "regista-bot"
git config user.email "regista-bot@users.noreply.github.com"
git add -A -- "$@"
git diff --cached --quiet && { echo "Niente da salvare"; exit 0; }
git commit -q -m "$msg"
for i in 1 2 3 4; do
  git pull --rebase -q && git push -q && { echo "Stato salvato"; exit 0; }
  git rebase --abort 2>/dev/null
  sleep $((i * 7))
done
echo "::error::Push dello stato fallito 4 volte: controlla conflitti su $*"
exit 1
