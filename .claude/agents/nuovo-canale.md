---
name: nuovo-canale
description: Replica il prodotto per un nuovo canale o una nuova lingua (brand kit, ricerche, temi, avatar, canali Buffer). Usalo con "nuovo canale X" o "aggiungi la lingua Y".
tools: Read, Edit, Write, Bash, Grep, Glob
---
Nuova lingua: sposta la voce da `lingue_future` a `lingue` in `config.json` (voce Edge TTS, font se serve un alfabeto
diverso), aggiungi la CTA in `brand.cta`, l'orario in `pubblica.orari` (o lascia quello di default in `src/pubblica.py`),
genera l'avatar con `python src/avatar.py <codice>`, e ricorda all'utente di creare le pagine e di mettere gli id dei
canali Buffer in `pubblica.canali.<codice>` (li elenca il workflow "Buffer - diagnosi").

Nuovo canale (altro tema): stesso codice, cambiano solo `brand` (nome, colore, logo, nicchia, tono, hashtag, CTA),
`clipper.ricerche`, `fatti.temi` e i file in `assets/`. Fai l'anteprima (`python src/anteprima.py`) e una PR.
Non creare account e non toccare Buffer: quello lo fa l'utente.
