"""Test veloci, senza chiavi e senza rete: girano su ogni Pull Request (workflow 'Controlli')."""
import os, sys, unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import comune, editor, pubblica, scopri  # noqa: E402


class Comune(unittest.TestCase):
    def test_attribuzione_cc_by_ha_link_e_licenza(self):
        t = comune.attribuzione({"licenza": "CC BY", "autore": "NASA Goddard", "titolo": "Sun", "url": "https://youtu.be/x"})
        self.assertIn("https://youtu.be/x", t)
        self.assertIn("CC BY 4.0", t)
        self.assertIn("NASA Goddard", t)

    def test_attribuzione_nasa(self):
        self.assertIn("does not endorse", comune.attribuzione({"licenza": "Public domain", "autore": "NASA"}))

    def test_hashtag_senza_doppioni_e_con_quelli_del_brand(self):
        h = comune.hashtag({"hashtags": ["#space", "space", "#Shorts"]}, {"brand": {"hashtag_fissi": ["#shorts"]}})
        self.assertEqual(h.count("#space"), 1)
        self.assertIn("#shorts", h)

    def test_niente_gta_nel_brand(self):
        cfg = comune.carica(comune.CONFIG, {})
        self.assertNotIn("gta", str(cfg).lower())


class Licenza(unittest.TestCase):
    def test_id_youtube(self):
        self.assertEqual(scopri.id_youtube("https://www.youtube.com/watch?v=em9cqXjEZ60"), "em9cqXjEZ60")
        self.assertEqual(scopri.id_youtube("https://youtu.be/em9cqXjEZ60"), "em9cqXjEZ60")

    def test_twitch_e_altri_siti_rifiutati(self):
        with self.assertRaises(scopri.LicenzaNonLibera):
            scopri.verifica("k", "https://www.twitch.tv/videos/123")

    def test_nasa_ammessa(self):
        self.assertEqual(scopri.verifica(None, "https://images.nasa.gov/details/x")["licenza"], "Public domain")

    def test_youtube_standard_rifiutato(self):
        finto = {"items": [{"status": {"license": "youtube"}, "snippet": {}}]}
        with mock.patch.object(scopri, "_get", return_value=finto):
            with self.assertRaises(scopri.LicenzaNonLibera):
                scopri.verifica("k", "https://youtu.be/em9cqXjEZ60")

    def test_youtube_cc_accettato(self):
        finto = {"items": [{"status": {"license": "creativeCommon"}, "snippet": {"channelTitle": "ESA", "title": "T"}}]}
        with mock.patch.object(scopri, "_get", return_value=finto):
            self.assertEqual(scopri.verifica("k", "https://youtu.be/em9cqXjEZ60")["autore"], "ESA")


class Scopritore(unittest.TestCase):
    def test_scarta_cgi_e_giochi(self):
        for titolo, cat in (("Houdini - Tornado FX Compilation (CGI VFX)", "28"), ("How to Air Roll in Rocket League", "20"),
                            ("Pen spinning Tornado tips", "22"), ("Goanimate Tornado", "1")):
            self.assertFalse(scopri.adatto({"snippet": {"title": titolo, "categoryId": cat}}), titolo)

    def test_accetta_natura_vera(self):
        self.assertTrue(scopri.adatto({"snippet": {"title": "Massive tornado caught on camera", "categoryId": "25"}}))
        self.assertTrue(scopri.adatto({"snippet": {"title": "Humpback whale breach", "categoryId": "15"}}))


class Pubblica(unittest.TestCase):
    def test_senza_mappa_solo_inglese_su_tutti_i_canali(self):
        self.assertIsNone(pubblica.canali_lingua("en", {}))
        self.assertEqual(pubblica.canali_lingua("it", {}), [])
        self.assertFalse(pubblica.ha_destinazione("it", {"canali": {"it": []}}))

    def test_mappa_per_lingua(self):
        cfg = {"canali": {"en": ["a"], "it": ["b"]}}
        self.assertEqual(pubblica.canali_lingua("it", cfg), ["b"])
        self.assertEqual(pubblica.canali_lingua("es", cfg), [])

    def test_ogni_lingua_ha_il_suo_fuso(self):
        _, k_it = pubblica.prossimo_slot("it", set(), {"orari": {"en": {"tz": "America/New_York", "ore": ["12:00"]}}})
        self.assertTrue(k_it.startswith("it|"))

    def test_testi_dal_gruppo(self):
        g = {"fonte": {"licenza": "CC BY", "autore": "A", "url": "u", "titolo": "t"},
             "versioni": {"it": {"titolo": "Ciao", "descrizione": "d", "hashtags": ["#a"]}}}
        titolo, _, tags, credito, lingua = pubblica.testi_gruppo(g, "it")
        self.assertEqual((titolo, tags, lingua), ("Ciao", "#a", "it"))
        self.assertIn("CC BY", credito)


class Editor(unittest.TestCase):
    def test_colore_ass(self):
        self.assertEqual(editor.ass_colore("#FFD400"), "&H0000D4FF")


class Fonti(unittest.TestCase):
    def test_nasa_pesante_prova_la_versione_piu_leggera_e_chiave_rifiutata_si_spegne(self):
        import fonti
        chiamate, scaricati = [], []

        def pixabay(q, usati, chiave):
            chiamate.append(q)
            raise RuntimeError("HTTP 400: [ERROR 400] Invalid API key.")

        def scarica(src, dest, max_mb=200):
            scaricati.append(src)
            if "medium" in src:
                raise RuntimeError("file troppo grande (928 MB)")

        vecchi = fonti.pixabay, fonti.scarica, fonti.pexels, fonti.nasa
        fonti.pixabay, fonti.scarica = pixabay, scarica
        fonti.pexels = lambda q, u, c: None
        fonti.nasa = lambda q, u: {"id": "nasa:x", "src": "a~medium.mp4", "alt": ["a~medium.mp4", "a~small.mp4"],
                                   "credito": "NASA", "fonte": "NASA"}
        fonti.SPENTE.clear()
        try:
            _, info = fonti.trova_clip("jupiter", "stock", set(), {"pixabay": "k"}, "/tmp", 0)
            fonti.trova_clip("saturn", "stock", set(), {"pixabay": "k"}, "/tmp", 1)
        finally:
            fonti.pixabay, fonti.scarica, fonti.pexels, fonti.nasa = vecchi
            fonti.SPENTE.clear()
        self.assertEqual(info["src"], "a~small.mp4")
        self.assertEqual(chiamate, ["jupiter"])  # Pixabay non si riprova dopo la chiave rifiutata


class FormatRiferimenti(unittest.TestCase):
    def test_testata_fissa_e_numero_con_nome(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            ass = os.path.join(d, "s.ass")
            editor.scrivi_ass(ass, [[(0, 1, "ciao")]], "#3 Bootes void", 4.0, "Footage: NASA", testata="5 scary things")
            testo = open(ass, encoding="utf-8").read()
        self.assertIn("Testa,,0,0,0,,5 SCARY THINGS", testo)
        self.assertIn("Rank,,0,0,410,,#3", testo)
        self.assertIn("BOOTES VOID", testo)


if __name__ == "__main__":
    unittest.main()
