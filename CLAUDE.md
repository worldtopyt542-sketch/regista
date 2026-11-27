# Autoclipping-video virali di massa — regole del progetto (per Claude)
- Rispondi in italiano. Domande all'utente: brevi, sempre a scelta multipla (A, B, C, D...).
- Risparmia token: niente spiegazioni lunghe, agisci.
- Tema: Planet Off Scale = spazio/lanci, animali/natura, momenti incredibili. SOLO video Creative Commons BY (>=1M views, src/scopri.py) o pubblico dominio: niente copyright. Credito 'Autore (CC BY)' sempre. Obiettivo: clip virali, intervento umano minimo.
- Pipeline principale: `src/clipper.py` (workflow "Autoclipper Planet Off Scale"; vecchi canali GTA in config clipper.canali_gta, spenti). `src/regista.py` = news Top 5 GTA 6.
- Top 5 (src/top5.py): 2 al giorno dai momenti virali delle live, voce narrante scritta da Gemini guardando i fotogrammi. `src/regista.py` (news) solo manuale.
- Pubblicazione: `src/pubblica.py` ogni 15 min via Buffer (`src/buffer.py`, GraphQL api.buffer.com); video messi online come asset di Release GitHub (MEDIA_REPO/MEDIA_TOKEN o repo stesso se pubblico). ✅ = prossimo orario migliore; report 20 UTC.
- Stato: archivio.json (news), clipper.json (clipper), pubblica.json (pubblicatore).
- Collaborazione (2 sviluppatori, ognuno col suo Claude Code): leggi COLLABORARE.md. Mai commit diretti su main: branch `nome/cosa` + Pull Request; collega la PR all'Issue; non modificare a mano archivio.json/clipper.json/pubblica.json.
