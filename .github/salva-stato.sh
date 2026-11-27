#!/usr/bin/env bash
# Salva i file di stato del bot sul ramo `stato` (main e' protetto: solo Pull Request).
# Ogni workflow scrive solo i SUOI file; pronte/ riceve solo file nuovi (mai cancellati da qui, tranne i gruppi
# piu' vecchi di 21 giorni), cosi' due workflow che salvano insieme non si cancellano il lavoro a vicenda.
# Riprova 4 volte; se non ce la fa, il workflow diventa rosso (prima era "push || true" e lo stato si perdeva).
# Uso: .github/salva-stato.sh "messaggio" file1 [file2 ...]
set -u
msg="$1"; shift
git config user.name "regista-bot"
git config user.email "regista-bot@users.noreply.github.com"
for i in 1 2 3 4; do
  dir=$(mktemp -d)
  if git fetch -q --depth=1 origin stato 2>/dev/null; then base=FETCH_HEAD; else base=HEAD; fi
  git worktree add -q --detach "$dir" "$base" || exit 1
  for f in "$@"; do
    if [ -d "$f" ]; then
      mkdir -p "$dir/$f" && cp -r "$f/." "$dir/$f/"
      limite=$(date -u -d '21 days ago' +%y%m%d)
      for g in "$dir/$f"/*.json; do
        [ -e "$g" ] || continue
        n=$(basename "$g"); [[ "${n:0:6}" =~ ^[0-9]{6}$ ]] && [[ "${n:0:6}" < "$limite" ]] && rm -f "$g"
      done
    elif [ -e "$f" ]; then
      cp "$f" "$dir/$f"
    fi
  done
  ( cd "$dir" && git add -A -- "$@" && { git diff --cached --quiet && echo "Niente da salvare" || git commit -q -m "$msg"; } \
      && git push -q origin HEAD:refs/heads/stato )
  ok=$?
  git worktree remove --force "$dir"
  [ $ok -eq 0 ] && { echo "Stato salvato sul ramo stato"; exit 0; }
  sleep $((i * 7))
done
echo "::error::Salvataggio dello stato fallito 4 volte (ramo stato): $*"
exit 1
