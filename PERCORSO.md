# Percorso — Planet Off Scale

La strada del canale, a target. Le percentuali contano solo cio' che e' **verificato** (girato davvero su
Actions o pubblicato davvero). Formato rigido: `## Target N — nome · **X%**` e righe con ✅ o ⬜, perche' la
mappa di Fra (Egghead) lo legge con uno script. Lo aggiornate tutti e due, nella stessa PR del lavoro.

Aggiornato: 27 novembre 2026

---

## Target 1 — Il format, uno stampo solo · **60%**

| Task | Stato | Nota |
|---|---|---|
| Brand kit in config.json, niente nome del canale nel codice | ✅ | PR #4 |
| Template 9:16: gancio, karaoke, logo, barra, credito, CTA tradotta | ✅ | anteprima locale |
| Avatar per lingua dalla stessa matrice | ✅ | assets/avatar_*.png |
| Giro vero su Actions dopo il merge, video controllati a occhio | ⬜ | |
| Anteprima con un video CC vero nella CI | ⬜ | |

## Target 2 — I format · **55%**

| Task | Stato | Nota |
|---|---|---|
| Clip da video YouTube CC BY (audio + fotogrammi) | ✅ | |
| Top 5 con voce narrante | ✅ | solo EN |
| Off Scale Facts con filmati NASA | ✅ | primo giro su Actions 27/11: EN/IT/ES ok |
| Top 5 in IT ed ES (voce tradotta per segmento) | ⬜ | |
| Facts rifatto sugli Shorts di riferimento di Fra | ✅ | testata, numero + nome, whoosh, tappeto, loop |
| Scaletta di 100 video spazio, seguita in ordine dal bot | ✅ | scaletta.json |
| Ogni voce della scaletta con filmati in alta qualita' | ⬜ | workflow "Controlla i filmati della scaletta" |
| Formato Storia (un soggetto in 5 battute) | ✅ | scaletta: formato storia |
| Space Sounds (sonificazioni NASA come payoff) | ⬜ | dai riferimenti |
| Scale Check (confronti di grandezza) | ⬜ | FORMAT.md |
| Long cut 60-90 s | ⬜ | per i programmi che pagano solo > 1 min |

## Target 3 — Senza rischi · **88%**

| Task | Stato | Nota |
|---|---|---|
| Licenza CC verificata anche per i link manuali | ✅ | scopri.verifica |
| Attribuzione completa nel post | ✅ | comune.attribuzione |
| Bot Telegram solo per il proprietario | ✅ | |
| Errori temporanei non bruciano i video | ✅ | 3 tentativi |
| Stato salvato con retry, niente push silenziosi | ✅ | salva-stato.sh |
| Una clip mancante o troppo pesante non fa perdere il video | ✅ | fonti.trova_clip |
| Clip NASA senza titoli, loghi o conferenze stampa (controllo Gemini) | ✅ | fonti.pulisci_clip |
| Foto NASA ad alta risoluzione (Hubble, Webb) come clip con zoom | ✅ | fonti.nasa_foto |
| Repository privato o media su un repo separato | ⬜ | oggi e' pubblico |

## Target 4 — Tante pagine, tante lingue · **40%**

| Task | Stato | Nota |
|---|---|---|
| Pagine EN su TikTok, Instagram, YouTube | ✅ | |
| Un ✅ per tutte le lingue, canali per lingua | ✅ | pubblica.canali |
| Pagine IT su TikTok, Instagram, YouTube collegate a Buffer | ⬜ | |
| Pagine ES su TikTok, Instagram, YouTube collegate a Buffer | ⬜ | |
| Auto-pubblicazione sopra soglia accesa | ⬜ | auto_pubblica_sopra |

## Target 5 — Crescita misurata · **0%**

| Task | Stato | Nota |
|---|---|---|
| Views per video, formato, lingua e ricerca salvate ogni giorno | ⬜ | |
| Ricerche e temi pesati su cio' che funziona | ⬜ | |
| Prima settimana con almeno 10 video al giorno pubblicati | ⬜ | |

**Il prossimo passo:** unire la PR #4, lanciare a mano "Autoclipper" e "Off Scale Facts" e guardare i video su Telegram.
