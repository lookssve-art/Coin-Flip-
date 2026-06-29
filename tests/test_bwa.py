"""Tests fuer die BWA / den Monatsabschluss."""

import os
import sys
import unittest
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.abschluss import erstelle_bwa, render_bwa_text


@dataclass
class _EUER:
    einnahmen_gesamt: Decimal
    ausgaben_je_kategorie: dict
    gewinn: Decimal


@dataclass
class _Sale:
    datum: date
    brutto: Decimal


class TestBWA(unittest.TestCase):
    def setUp(self):
        self.euer = _EUER(
            einnahmen_gesamt=Decimal("1000.00"),
            ausgaben_je_kategorie={"wareneinkauf": Decimal("400.00"),
                                   "gebuehren": Decimal("130.00"),
                                   "versand": Decimal("70.00")},
            gewinn=Decimal("400.00"))
        self.sales = [_Sale(date(2026, 6, 5), Decimal("600.00")),
                      _Sale(date(2026, 6, 20), Decimal("400.00")),
                      _Sale(date(2026, 7, 2), Decimal("0.00"))]

    def test_rohertrag_und_quoten(self):
        b = erstelle_bwa(self.sales, self.euer)
        self.assertEqual(b.umsatz, Decimal("1000.00"))
        self.assertEqual(b.wareneinkauf, Decimal("400.00"))
        self.assertEqual(b.rohertrag, Decimal("600.00"))
        # Kosten ohne Wareneinkauf = 130 + 70 = 200
        self.assertEqual(b.kosten_gesamt, Decimal("200.00"))
        self.assertEqual(b.gewinn, Decimal("400.00"))
        self.assertEqual(b.rohertragsquote, Decimal("60.0"))   # 600/1000
        self.assertEqual(b.gewinnmarge, Decimal("40.0"))       # 400/1000
        self.assertEqual(b.kostenquote, Decimal("60.0"))       # (200+400)/1000

    def test_kosten_haben_konten(self):
        b = erstelle_bwa(self.sales, self.euer, rahmen="skr03")
        self.assertEqual(b.kosten_je_kategorie["gebuehren"]["konto"], "4760")
        self.assertEqual(b.kosten_je_kategorie["versand"]["konto"], "4910")
        # absteigend sortiert: gebuehren (130) vor versand (70)
        self.assertEqual(list(b.kosten_je_kategorie.keys()), ["gebuehren", "versand"])

    def test_monatsverlauf(self):
        b = erstelle_bwa(self.sales, self.euer)
        self.assertEqual(b.monatlich["2026-06"]["umsatz"], Decimal("1000.00"))
        self.assertEqual(b.monatlich["2026-06"]["anzahl"], 2)
        self.assertIn("2026-07", b.monatlich)

    def test_render_enthaelt_kerngroessen(self):
        txt = render_bwa_text(erstelle_bwa(self.sales, self.euer))
        self.assertIn("Umsatz", txt)
        self.assertIn("Rohertrag", txt)
        self.assertIn("GEWINN", txt)
        self.assertIn("2026-06", txt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
