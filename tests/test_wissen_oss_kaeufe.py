"""Tests: Geschaeftsbeginn-Cutoff, eBay-Kaeufe, OSS-Schwelle, Duden, Bot /duden."""

import os
import sys
import unittest
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.util.datum import ab_geschaeftsbeginn, ist_eu_b2c_fernverkauf, parse_iso
from src.integrations import normalisiere_kaeufe
from src.models import PlatformSale, Source, TaxScheme
from src.tax import journalisiere_verkaeufe
from src.wissen import Duden
from src.interface import TelegramBot
from src.review import ReviewQueue


class TestCutoff(unittest.TestCase):
    def test_ab_geschaeftsbeginn(self):
        beginn = date(2026, 6, 1)
        self.assertTrue(ab_geschaeftsbeginn(date(2026, 6, 1), beginn))
        self.assertTrue(ab_geschaeftsbeginn(date(2026, 7, 1), beginn))
        self.assertFalse(ab_geschaeftsbeginn(date(2026, 5, 31), beginn))
        self.assertFalse(ab_geschaeftsbeginn(None, beginn))     # ohne Datum: ausschliessen
        self.assertTrue(ab_geschaeftsbeginn(date(2020, 1, 1), None))  # kein Beginn: alles

    def test_eu_b2c(self):
        self.assertTrue(ist_eu_b2c_fernverkauf("FR"))
        self.assertFalse(ist_eu_b2c_fernverkauf("DE"))   # Inland
        self.assertFalse(ist_eu_b2c_fernverkauf("US"))   # Drittland


class TestEbayKaeufe(unittest.TestCase):
    def test_filter_ab_beginn_und_letzter_gewinnt(self):
        rows = [
            {"product_id": "P1", "date": "2026-05-15", "price": "40.00"},  # vor Gruendung
            {"product_id": "P1", "date": "2026-06-10", "price": "70.00"},  # zaehlt
            {"product_id": "P1", "date": "2026-06-20", "price": "72.00"},  # letzter -> gewinnt
            {"product_id": "P2", "date": "2026-06-01", "price": "10,50"},
        ]
        preise, ignoriert = normalisiere_kaeufe(rows, ab=date(2026, 6, 1))
        self.assertEqual(preise["P1"], Decimal("72.00"))
        self.assertEqual(preise["P2"], Decimal("10.50"))
        self.assertEqual(len(ignoriert), 1)


class TestOssSchwelle(unittest.TestCase):
    def _sale(self, sid, brutto, land, business=False, scheme=TaxScheme.REGEL):
        return PlatformSale(id=sid, datum=date(2026, 6, 3), plattform=Source.EBAY,
                            brutto=Decimal(brutto), customer_country=land,
                            customer_is_business=business, tax_scheme=scheme)

    def test_oss_nur_eu_b2c_regelware(self):
        sales = [
            self._sale("A", "119", "FR"),                       # zaehlt (netto 100)
            self._sale("B", "119", "DE"),                       # Inland -> nein
            self._sale("C", "119", "US"),                       # Drittland -> nein
            self._sale("D", "119", "ES", business=True),        # B2B -> nein
            self._sale("E", "100", "IT", scheme=TaxScheme.DIFFERENZ),  # §25a -> ausgenommen
        ]
        j = journalisiere_verkaeufe(sales, {"_": Decimal("0")})
        self.assertEqual(j.oss_netto_eu_b2c, Decimal("100.00"))


class TestDuden(unittest.TestCase):
    def test_suche_findet_thema(self):
        d = Duden()
        hits = d.suche("wie lange muss ich rechnungen aufheben")
        self.assertTrue(hits)
        self.assertEqual(hits[0].schlagwort, "Aufbewahrungsfristen")

    def test_suche_paragraph(self):
        hits = Duden().suche("§25a marge")
        self.assertEqual(hits[0].schlagwort, "Differenzbesteuerung")

    def test_liste_nicht_leer(self):
        self.assertGreaterEqual(len(Duden().liste()), 10)


class TestBotDuden(unittest.TestCase):
    def _bot(self):
        return TelegramBot(token="x", review_queue=ReviewQueue(),
                           allowed_user_ids={1}, duden=Duden())

    def test_duden_ohne_arg_listet_themen(self):
        antwort = self._bot().handle_command("/duden", user_id=1)
        self.assertIn("Themen", antwort)
        self.assertIn("E-Rechnung", antwort)

    def test_duden_frage_liefert_kb(self):
        antwort = self._bot().handle_command("/duden kleinunternehmer grenze", user_id=1)
        self.assertIn("25.000", antwort)
        self.assertIn("§ 19 UStG", antwort)

    def test_duden_unautorisiert(self):
        antwort = self._bot().handle_command("/duden gobd", user_id=999)
        self.assertIn("Nicht autorisiert", antwort)


if __name__ == "__main__":
    unittest.main(verbosity=2)
