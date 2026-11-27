#!/usr/bin/env bash
# Porta nella cartella di lavoro i file di stato del bot dal ramo `stato`.
# Il ramo main e' protetto ("solo tramite Pull Request"): il bot non puo' scriverci, quindi lo stato vive a parte.
# Se il ramo `stato` non esiste ancora (primo giro), restano i file di main.
set -u
STATO_FILE="archivio.json clipper.json pubblica.json pronte"
if ! git fetch -q --depth=1 origin stato 2>/dev/null; then
  echo "Ramo stato non ancora creato: uso lo stato che c'e' su main"
  exit 0
fi
for f in $STATO_FILE; do
  git checkout FETCH_HEAD -- "$f" 2>/dev/null && echo "stato: $f dal ramo stato" || echo "stato: $f non c'e' nel ramo stato"
done
git reset -q
