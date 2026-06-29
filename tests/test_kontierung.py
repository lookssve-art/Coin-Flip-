"""Tests fuer die automatische Kontierung (SKR03/SKR04)."""

import os
import sys
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.kontierung import kontiere, konto_fuer, SKR03, SKR04


class TestKontierung(unittest.TestCase):
    def test_skr03_und_skr04_unterscheiden_sich(self):
        self.assertEqual(konto_fuer("wareneinkauf", rahmen="skr03"), "3200")
        self.assertEqual(konto_fuer("wareneinkauf", rahmen="skr04"), "5200")
        self.assertEqual(konto_fuer("versand", rahmen="skr03"), "4910")

    def test_buchungssatz_betrag_und_ust(self):
        b = kontiere("gebuehren", Decimal("22.40"), rahmen="skr03")
        self.assertEqual(b.konto, "4760")
        self.assertEqual(b.betrag, Decimal("22.40"))
        self.assertEqual(b.ust_schluessel, "9")
        self.assertTrue(b.sicher)

    def test_unbekannte_kategorie_geht_in_review(self):
        b = kontiere("voellig-neu", Decimal("5"))
        self.assertEqual(b.konto, "")
        self.assertFalse(b.sicher)
        self.assertIn("Review", b.hinweis)

    def test_config_override(self):
        cfg = {"skr03": {"wareneinkauf": "3300"}}
        self.assertEqual(konto_fuer("wareneinkauf", rahmen="skr03", config=cfg), "3300")
        # nicht ueberschriebene bleiben Default
        self.assertEqual(konto_fuer("versand", rahmen="skr03", config=cfg), "4910")

    def test_kleinunternehmer_und_differenz_erloeskonten(self):
        self.assertEqual(konto_fuer("erloese_kleinunternehmer", rahmen="skr03"), "8195")
        self.assertEqual(konto_fuer("erloese_differenz", rahmen="skr04"), "4200")

    def test_alle_master_prompt_kategorien_haben_konto(self):
        # Punkt 5 des Master-Prompts: diese Kategorien muessen zugeordnet sein.
        noetig = ["wareneinkauf", "versand", "gebuehren", "software", "hosting",
                  "werbung", "telefon", "internet", "fahrzeug", "bewirtung",
                  "reise", "buero", "versicherung", "steuerberater",
                  "bankgebuehren", "zinsen", "privatentnahme", "einlage"]
        for kat in noetig:
            self.assertTrue(konto_fuer(kat, rahmen="skr03"), f"SKR03 fehlt: {kat}")
            self.assertTrue(konto_fuer(kat, rahmen="skr04"), f"SKR04 fehlt: {kat}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
