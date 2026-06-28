"""Tests: USt-VA-Kennzahlen, EÜR-Übersicht, erweiterter Duden."""

import os
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tax import (ustva_kennzahlen, schreibe_ustva_csv, euer_uebersicht,
                     schreibe_euer_csv, journalisiere_verkaeufe)
from src.models import PlatformSale, Source, TaxScheme, Receipt
from src.wissen import Duden


class TestUStVaKennzahlen(unittest.TestCase):
    def test_kennzahlen_regelbesteuerung(self):
        k = ustva_kennzahlen("Q2/2026", kleinunternehmer=False,
                             netto_19=Decimal("1000.00"), netto_7=Decimal("100.00"),
                             vorsteuer=Decimal("50.00"))
        self.assertEqual(k.kennzahlen["81"], Decimal("1000"))   # volle Euro
        self.assertEqual(k.kennzahlen["86"], Decimal("100"))
        self.assertEqual(k.ust_19, Decimal("190.00"))
        self.assertEqual(k.ust_7, Decimal("7.00"))
        # Zahllast = 190 + 7 - 50 = 147
        self.assertEqual(k.kennzahlen["83"], Decimal("147.00"))

    def test_kleinunternehmer_keine_kennzahlen(self):
        k = ustva_kennzahlen("Q2/2026", kleinunternehmer=True, netto_19=Decimal("1000"))
        self.assertEqual(k.kennzahlen, {})
        self.assertTrue(any("§ 19" in h for h in k.hinweise))

    def test_csv_schreiben(self):
        k = ustva_kennzahlen("Q2/2026", kleinunternehmer=False, netto_19=Decimal("1000"))
        with tempfile.TemporaryDirectory() as d:
            pfad = os.path.join(d, "ustva.csv")
            schreibe_ustva_csv(pfad, k)
            with open(pfad, encoding="utf-8") as fh:
                inhalt = fh.read()
            self.assertIn("81;Steuerpflichtige", inhalt)
            self.assertIn("83;", inhalt)

    def test_differenz_netto_fliesst_in_kz81(self):
        sales = [PlatformSale(id="V1", datum=date(2026, 6, 3), plattform=Source.EBAY,
                              brutto=Decimal("120"), product_id="P1",
                              tax_scheme=TaxScheme.DIFFERENZ)]
        j = journalisiere_verkaeufe(sales, {"P1": Decimal("70")})
        # Netto-Marge 42,02 muss in der 19%-Basis landen
        self.assertEqual(j.differenz_netto, Decimal("42.02"))


class TestEuer(unittest.TestCase):
    def _receipt(self, kat, brutto, netto):
        return Receipt(id="R", datum=date(2026, 6, 3), haendler="X",
                       brutto=Decimal(brutto), netto=Decimal(netto),
                       ust_satz=Decimal("19"), ust_betrag=Decimal("0"), kategorie=kat)

    def _sale(self, brutto):
        return PlatformSale(id="S", datum=date(2026, 6, 3), plattform=Source.EBAY,
                            brutto=Decimal(brutto))

    def test_euer_kleinunternehmer_brutto(self):
        r = euer_uebersicht([self._sale("200")],
                            [self._receipt("wareneinkauf", "70", "58.82"),
                             self._receipt("buero", "30", "25.21")],
                            kleinunternehmer=True, zeitraum="2026")
        self.assertEqual(r.einnahmen_gesamt, Decimal("200.00"))
        self.assertEqual(r.ausgaben_je_kategorie["wareneinkauf"], Decimal("70.00"))
        self.assertEqual(r.ausgaben_gesamt, Decimal("100.00"))
        self.assertEqual(r.gewinn, Decimal("100.00"))

    def test_gewst_freibetrag_warnung(self):
        r = euer_uebersicht([self._sale("30000")], [], kleinunternehmer=True, zeitraum="2026")
        self.assertTrue(r.ueber_gewst_freibetrag)
        self.assertTrue(any("Gewerbesteuer" in h for h in r.hinweise))

    def test_csv(self):
        r = euer_uebersicht([self._sale("200")], [self._receipt("buero", "30", "25")],
                            kleinunternehmer=True, zeitraum="2026")
        with tempfile.TemporaryDirectory() as d:
            pfad = os.path.join(d, "euer.csv")
            schreibe_euer_csv(pfad, r)
            with open(pfad, encoding="utf-8") as fh:
                self.assertIn("Gewinn", fh.read())


class TestDudenErweitert(unittest.TestCase):
    def test_neue_themen_durchsuchbar(self):
        d = Duden()
        for frage, erwartet in [
            ("was muss auf die rechnung", "Rechnungspflichtangaben"),
            ("kleinbetragsrechnung 250", "Kleinbetragsrechnung"),
            ("afa abschreibung nutzungsdauer", "AfA / Abschreibung"),
            ("gwg 800 euro sofort", "GWG"),
            ("storno refund buchen", "Storno / Refund buchen"),
            ("ist versteuerung zahlungseingang", "Ist- vs. Soll-Versteuerung"),
        ]:
            hits = d.suche(frage)
            self.assertTrue(hits, frage)
            self.assertEqual(hits[0].schlagwort, erwartet, frage)

    def test_mindestens_25_themen(self):
        self.assertGreaterEqual(len(Duden().liste()), 25)


if __name__ == "__main__":
    unittest.main(verbosity=2)
