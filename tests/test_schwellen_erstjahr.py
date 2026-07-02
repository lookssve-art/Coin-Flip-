"""Test: Kleinunternehmer-Grenze im Gruendungsjahr = 25.000 EUR (§19 UStG 2025)."""

import os
import sys
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tax import SchwellenMonitor


class TestErstjahrGrenze(unittest.TestCase):
    def setUp(self):
        self.m = SchwellenMonitor(warnung_ab_prozent=Decimal("80"))

    def test_grenze_ist_25000(self):
        s = self.m.kleinunternehmer_erstjahr(Decimal("10000"))
        self.assertEqual(s.grenze, Decimal("25000"))

    def test_warnung_ab_80_prozent(self):
        self.assertFalse(self.m.kleinunternehmer_erstjahr(Decimal("19000")).warnung)  # 76%
        self.assertTrue(self.m.kleinunternehmer_erstjahr(Decimal("20000")).warnung)   # 80%

    def test_ueberschreitung(self):
        s = self.m.kleinunternehmer_erstjahr(Decimal("25000.01"))
        self.assertTrue(s.ueberschritten)

    def test_unterschied_zu_etabliert(self):
        # etablierter Betrieb: 100k-Grenze -> 30k ist noch keine Warnung
        self.assertFalse(self.m.kleinunternehmer_laufend(Decimal("30000")).warnung)
        # Gruendungsjahr: 30k ist laengst ueberschritten
        self.assertTrue(self.m.kleinunternehmer_erstjahr(Decimal("30000")).ueberschritten)


if __name__ == "__main__":
    unittest.main(verbosity=2)
