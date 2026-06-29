"""Tests fuer die Plausibilitaets- und Dublettenpruefung."""

import os
import sys
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pruefung import (pruefe_iban, pruefe_ust_id, pruefe_rechnung_arithmetik,
                          pruefe_pflichtfelder, ist_dublette, dubletten_schluessel,
                          Schwere)


class TestIban(unittest.TestCase):
    def test_gueltige_iban(self):
        # offizielle Beispiel-IBANs (ISO 7064 mod-97 = 1)
        self.assertTrue(pruefe_iban("DE89370400440532013000").ok)
        self.assertTrue(pruefe_iban("GB82 WEST 1234 5698 7654 32").ok)

    def test_falsche_pruefsumme(self):
        self.assertEqual(pruefe_iban("DE89370400440532013001").schwere, Schwere.FEHLER)

    def test_falsche_laenge(self):
        self.assertEqual(pruefe_iban("DE8937040044").schwere, Schwere.FEHLER)

    def test_leer_ist_hinweis(self):
        self.assertEqual(pruefe_iban("").schwere, Schwere.HINWEIS)


class TestUstId(unittest.TestCase):
    def test_gueltiges_format(self):
        self.assertTrue(pruefe_ust_id("DE123456789").ok)
        self.assertTrue(pruefe_ust_id("ATU12345678").ok)

    def test_falsches_format(self):
        self.assertEqual(pruefe_ust_id("DE12345").schwere, Schwere.FEHLER)

    def test_unbekanntes_land_hinweis(self):
        self.assertEqual(pruefe_ust_id("XX123").schwere, Schwere.HINWEIS)


class TestArithmetik(unittest.TestCase):
    def test_stimmig(self):
        self.assertTrue(pruefe_rechnung_arithmetik("100.00", "19.00", "119.00").ok)

    def test_innerhalb_toleranz(self):
        self.assertTrue(pruefe_rechnung_arithmetik("100.00", "19.00", "119.01").ok)

    def test_unstimmig(self):
        b = pruefe_rechnung_arithmetik("100.00", "19.00", "130.00")
        self.assertEqual(b.schwere, Schwere.FEHLER)


class TestPflichtfelder(unittest.TestCase):
    def test_fehlende_felder(self):
        befunde = pruefe_pflichtfelder({"a": 1, "b": ""}, ("a", "b", "c"))
        fehler = [x for x in befunde if x.schwere == Schwere.FEHLER]
        self.assertEqual({x.feld for x in fehler}, {"b", "c"})

    def test_alles_da(self):
        befunde = pruefe_pflichtfelder({"a": 1}, ("a",))
        self.assertTrue(befunde[0].ok)


class TestDubletten(unittest.TestCase):
    def test_erkennt_dublette(self):
        a = {"rechnungsnummer": "RE-1", "brutto": "119.00", "datum": "2026-06-01",
             "lieferant": "ACME"}
        b = dict(a)  # gleiche Werte
        bekannt = {dubletten_schluessel(a)}
        self.assertTrue(ist_dublette(b, bekannt))

    def test_andere_nummer_keine_dublette(self):
        a = {"rechnungsnummer": "RE-1", "brutto": "119.00", "datum": "2026-06-01"}
        b = {"rechnungsnummer": "RE-2", "brutto": "119.00", "datum": "2026-06-01"}
        self.assertFalse(ist_dublette(b, {dubletten_schluessel(a)}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
