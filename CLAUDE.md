# Regole del progetto (per Claude)
- Rispondi in italiano. Domande all'utente: brevi, sempre a scelta multipla (A, B, C, D...).
- Risparmia token: niente spiegazioni lunghe, agisci.
- Tema: GTA 6 e reaction degli streamer. Obiettivo: clip virali, intervento umano minimo.
- Pipeline principale: `src/clipper.py` (workflow "Autoclipper GTA 6"). `src/regista.py` = news Top 5 GTA 6.
- News GTA 6: `src/regista.py` (2 al giorno, mattina). Solo inglese per ora; altre lingue pronte in `lingue_future`.
- Pubblicazione: `src/pubblica.py` ogni 15 min; ✅ = programma nel prossimo orario migliore della lingua; report 20 UTC.
- Stato: archivio.json (news), clipper.json (clipper), pubblica.json (pubblicatore).
