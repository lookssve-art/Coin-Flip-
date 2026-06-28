"""Tests fuer Import-Adapter und Reconciliation-Grundlogik (MVP-Punkt 2)."""

import os
import sys
import unittest
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.imports import importiere_bank_transaktionen, importiere_ebay_verkaeufe, idempotency_key
from src.imports.ebay import netto_auszahlung
from src.models import Receipt, Source, TaxScheme
from src.reconciliation import Reconciler, MatchStatus


def _receipt(rid, datum, brutto, kategorie="wareneinkauf"):
    return Receipt(id=rid, datum=datum, haendler="X", brutto=Decimal(brutto),
                   netto=Decimal(brutto), ust_satz=Decimal("19"),
                   ust_betrag=Decimal("0"), kategorie=kategorie)


class TestBankImport(unittest.TestCase):
    def test_normalisierung_und_vorzeichen(self):
        rows = [
            {"date": "2026-06-01", "amount": "-70,00", "description": "Ankauf"},
            {"date": "2026-06-02", "amount": 120.0, "label": "eBay Auszahlung"},
        ]
        txs = importiere_bank_transaktionen(rows)
        self.assertEqual(len(txs), 2)
        self.assertEqual(txs[0].betrag, Decimal("-70.00"))
        self.assertEqual(txs[0].datum, date(2026, 6, 1))
        self.assertEqual(txs[1].betrag, Decimal("120.0"))

    def test_idempotenz_dedupliziert(self):
        row = {"date": "2026-06-01", "amount": "-70,00", "description": "Ankauf"}
        txs = importiere_bank_transaktionen([row, dict(row)])
        self.assertEqual(len(txs), 1)  # identische Zeile nur einmal

    def test_idempotency_key_stabil(self):
        k1 = idempotency_key(date(2026, 6, 1), Decimal("-70.00"), "Ankauf  Karte")
        k2 = idempotency_key(date(2026, 6, 1), Decimal("-70.00"), "ankauf karte")
        self.assertEqual(k1, k2)


class TestEbayImport(unittest.TestCase):
    def test_felder_und_schemes(self):
        rows = [{"id": "S1", "date": "2026-06-03", "gross": "120.00", "fees": "15.60",
                 "buyer_country": "fr", "tax_scheme": "differenz"}]
        sales = importiere_ebay_verkaeufe(rows)
        s = sales[0]
        self.assertEqual(s.plattform, Source.EBAY)
        self.assertEqual(s.tax_scheme, TaxScheme.DIFFERENZ)
        self.assertEqual(s.customer_country, "FR")
        self.assertEqual(netto_auszahlung(s), Decimal("104.40"))


class TestReconciliation(unittest.TestCase):
    def test_exakter_treffer(self):
        tx = importiere_bank_transaktionen(
            [{"date": "2026-06-01", "amount": "-70.00", "description": "Ankauf"}])
        res = Reconciler().reconcile(tx, [_receipt("R1", date(2026, 6, 1), "70.00")])
        self.assertEqual(res[0].status, MatchStatus.MATCHED)
        self.assertEqual(res[0].receipt_id, "R1")
        self.assertEqual(res[0].buchungsjahr, 2026)

    def test_teilzahlung_geht_in_review(self):
        tx = importiere_bank_transaktionen(
            [{"date": "2026-06-01", "amount": "-40.00", "description": "Anzahlung"}])
        res = Reconciler().reconcile(tx, [_receipt("R1", date(2026, 6, 1), "70.00")])
        self.assertEqual(res[0].status, MatchStatus.REVIEW_REQUIRED)
        self.assertEqual(res[0].differenz, Decimal("-30.00"))

    def test_refund_erkennung(self):
        tx = importiere_bank_transaktionen(
            [{"date": "2026-06-05", "amount": "-120.00", "description": "Erstattung"}])
        res = Reconciler().reconcile(
            tx, [_receipt("R1", date(2026, 6, 4), "120.00", kategorie="verkauf")])
        self.assertEqual(res[0].status, MatchStatus.REFUND)

    def test_unmatched_ausserhalb_toleranz(self):
        tx = importiere_bank_transaktionen(
            [{"date": "2026-07-01", "amount": "-70.00", "description": "Ankauf"}])
        res = Reconciler(datum_toleranz_tage=5).reconcile(
            tx, [_receipt("R1", date(2026, 6, 1), "70.00")])
        self.assertEqual(res[0].status, MatchStatus.UNMATCHED)

    def test_beleg_nur_einmal_verbraucht(self):
        txs = importiere_bank_transaktionen([
            {"id": "a", "date": "2026-06-01", "amount": "-70.00", "description": "Ankauf 1"},
            {"id": "b", "date": "2026-06-01", "amount": "-70.00", "description": "Ankauf 2"},
        ])
        res = Reconciler().reconcile(txs, [_receipt("R1", date(2026, 6, 1), "70.00")])
        self.assertEqual(res[0].status, MatchStatus.MATCHED)
        self.assertEqual(res[1].status, MatchStatus.UNMATCHED)  # Beleg schon verbraucht


if __name__ == "__main__":
    unittest.main(verbosity=2)
