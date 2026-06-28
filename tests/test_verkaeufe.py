"""Tests fuer die Verkaufs-Journalisierung (§ 25a-Marge + USt je Satz)."""

import os
import sys
import unittest
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import PlatformSale, Source, TaxScheme
from src.tax import journalisiere_verkaeufe


def _sale(sid, brutto, *, scheme=TaxScheme.REGEL, product_id=None, collected=0):
    return PlatformSale(
        id=sid, datum=date(2026, 6, 3), plattform=Source.EBAY,
        brutto=Decimal(brutto), product_id=product_id, tax_scheme=scheme,
        ebay_collected_vat=Decimal(collected))


class TestVerkaeufe(unittest.TestCase):
    def test_differenz_marge_und_ust(self):
        sales = [_sale("V1", "120", scheme=TaxScheme.DIFFERENZ, product_id="P1")]
        j = journalisiere_verkaeufe(sales, {"P1": Decimal("70")})
        self.assertEqual(len(j.differenz_eintraege), 1)
        artikel, marge = j.differenz_eintraege[0]
        self.assertEqual(artikel, "P1")
        self.assertEqual(marge.marge, Decimal("50.00"))
        self.assertEqual(j.differenz_ust, Decimal("7.98"))

    def test_differenz_ohne_einkaufspreis_geht_in_review(self):
        sales = [_sale("V2", "120", scheme=TaxScheme.DIFFERENZ, product_id="UNBEKANNT")]
        j = journalisiere_verkaeufe(sales, {})
        self.assertEqual(j.review_ids, ["V2"])
        self.assertEqual(len(j.differenz_eintraege), 0)

    def test_regel_ust_je_satz(self):
        # 119 brutto @ 19% -> 19,00 USt
        j = journalisiere_verkaeufe([_sale("V3", "119")], {})
        self.assertEqual(j.regel_ust_je_satz["19"], Decimal("19.00"))

    def test_deemed_supplier_nicht_doppelt(self):
        j = journalisiere_verkaeufe([_sale("V4", "119", collected="19.00")], {})
        self.assertEqual(j.regel_ust_je_satz, {})        # eigene USt nicht angesetzt
        self.assertEqual(j.deemed_supplier_ust, Decimal("19.00"))

    def test_refund_traegt_keine_ust(self):
        j = journalisiere_verkaeufe([_sale("V5", "0")], {})
        self.assertEqual(j.regel_ust_je_satz, {})
        self.assertEqual(j.differenz_ust, Decimal("0"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
