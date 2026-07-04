"""Tests fuer Warenbuch/Bestand + Lexware-Beleg-Parsing."""

import os
import sys
import unittest
from dataclasses import dataclass
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.warenbuch import erstelle_warenbuch, render_bestand_text
from src.integrations import parse_voucherlist


@dataclass
class _Sale:
    product_id: str
    product_name: str
    brutto: Decimal


class TestWarenbuch(unittest.TestCase):
    def test_bestand_und_marge(self):
        kaeufe = [
            {"product_id": "CHAR-1", "title": "Charizard", "preis": "40.00", "quelle": "ebay"},
            {"product_id": "CHAR-1", "title": "Charizard", "preis": "45.00", "quelle": "ebay"},
            {"product_id": "", "title": "Sammelbeleg", "preis": "100.00", "quelle": "lexware"},
        ]
        verkaeufe = [_Sale("CHAR-1", "Charizard", Decimal("120.00"))]
        w = erstelle_warenbuch(kaeufe, verkaeufe)
        self.assertEqual(w.einkauf_anzahl, 3)
        self.assertEqual(w.verkauf_anzahl, 1)
        self.assertEqual(w.einkauf_gesamt, Decimal("185.00"))
        self.assertEqual(w.verkauf_gesamt, Decimal("120.00"))
        # Charizard: 2 gekauft, 1 verkauft -> 1 im Bestand
        g = w.gruppen[[k for k in w.gruppen if "char" in k][0]]
        self.assertEqual(g.bestand, 1)
        self.assertEqual(g.einkauf_summe, Decimal("85.00"))
        self.assertEqual(g.verkauf_summe, Decimal("120.00"))
        self.assertEqual(g.marge, Decimal("35.00"))

    def test_render_text(self):
        w = erstelle_warenbuch([{"title": "X", "preis": "10", "quelle": "ebay"}], [])
        t = render_bestand_text(w)
        self.assertIn("Warenbuch", t)
        self.assertIn("Bestand", t)

    def test_komma_preis_crasht_nicht(self):
        # Website-Export liefert oft deutsche Kommazahlen.
        w = erstelle_warenbuch([{"title": "X", "preis": "12,34", "quelle": "ebay"}], [])
        self.assertEqual(w.einkauf_gesamt, Decimal("12.34"))

    def test_menge_zaehlt_im_verkauf(self):
        @dataclass
        class _S:
            product_id: str
            product_name: str
            brutto: Decimal
            menge: Decimal
        kaeufe = [{"product_id": "B-1", "title": "Booster", "preis": "10.00",
                   "quelle": "ebay"} for _ in range(3)]
        w = erstelle_warenbuch(kaeufe, [_S("B-1", "Booster", Decimal("45.00"), Decimal("3"))])
        self.assertEqual(w.verkauf_anzahl, 3)
        self.assertEqual(w.bestand_anzahl, 0)   # 3 gekauft, 3 verkauft

    def test_refund_zeile_ist_kein_verkauf(self):
        refund = _Sale("", "", Decimal("0"))
        w = erstelle_warenbuch([{"title": "X", "preis": "10", "quelle": "ebay"}], [refund])
        self.assertEqual(w.verkauf_anzahl, 0)
        self.assertEqual(w.bestand_anzahl, 1)


class TestLexwareVoucherParse(unittest.TestCase):
    def test_parse(self):
        raw = {"content": [
            {"id": "v1", "voucherType": "purchaseinvoice", "voucherStatus": "paid",
             "voucherNumber": "EK-1", "voucherDate": "2026-06-01T00:00:00.000+02:00",
             "contactName": "Kartenshop", "totalAmount": 123.45, "currency": "EUR"},
        ], "totalPages": 1}
        belege = parse_voucherlist(raw)
        self.assertEqual(len(belege), 1)
        self.assertEqual(belege[0]["datum"], "2026-06-01")
        self.assertEqual(belege[0]["betrag"], "123.45")
        self.assertEqual(belege[0]["kontakt"], "Kartenshop")
        self.assertEqual(belege[0]["typ"], "purchaseinvoice")

    def test_leer(self):
        self.assertEqual(parse_voucherlist({}), [])
        self.assertEqual(parse_voucherlist({"content": "x"}), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
