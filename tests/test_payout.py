"""Tests fuer die eBay-Payout-Reconciliation (Auszahlungen <-> Bank-Eingaenge)."""

import os
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.imports import importiere_bank_transaktionen
from src.reconciliation import (PayoutReconciler, PayoutStatus, Payout,
                                extrahiere_payouts)
from src.export import schreibe_payout_journal


def _bank(rows):
    return importiere_bank_transaktionen(rows)


class TestExtrahierePayouts(unittest.TestCase):
    def test_nur_payout_typ(self):
        roh = [
            {"transactionType": "SALE", "amount": {"value": "20"}},
            {"transactionType": "PAYOUT", "payoutId": "PO1",
             "payoutDate": "2026-06-07T00:00:00.000Z", "amount": {"value": "104.40"}},
        ]
        payouts = extrahiere_payouts(roh)
        self.assertEqual(len(payouts), 1)
        self.assertEqual(payouts[0].id, "PO1")
        self.assertEqual(payouts[0].betrag, Decimal("104.40"))
        self.assertEqual(payouts[0].datum, date(2026, 6, 7))


class TestPayoutReconciler(unittest.TestCase):
    def test_exakter_treffer(self):
        payouts = [Payout("PO1", date(2026, 6, 7), Decimal("104.40"))]
        txs = _bank([{"date": "2026-06-08", "amount": "104,40", "description": "eBay"}])
        res = PayoutReconciler().reconcile(payouts, txs)
        self.assertEqual(res[0].status, PayoutStatus.MATCHED)
        self.assertEqual(res[0].differenz, Decimal("0"))

    def test_betragsdifferenz_markiert(self):
        payouts = [Payout("PO1", date(2026, 6, 7), Decimal("104.40"))]
        txs = _bank([{"date": "2026-06-08", "amount": "100,00", "description": "eBay"}])
        res = PayoutReconciler().reconcile(payouts, txs)
        self.assertEqual(res[0].status, PayoutStatus.DIFFERENZ)
        self.assertEqual(res[0].differenz, Decimal("-4.40"))

    def test_kein_bankeingang(self):
        payouts = [Payout("PO1", date(2026, 6, 7), Decimal("104.40"))]
        txs = _bank([{"date": "2026-07-20", "amount": "104,40", "description": "eBay"}])
        res = PayoutReconciler(datum_toleranz_tage=5).reconcile(payouts, txs)
        self.assertEqual(res[0].status, PayoutStatus.UNMATCHED)

    def test_ausgaben_zaehlen_nicht_als_payout(self):
        payouts = [Payout("PO1", date(2026, 6, 7), Decimal("70.00"))]
        # negativer Betrag (Ausgabe) darf NICHT als Auszahlung gematcht werden
        txs = _bank([{"date": "2026-06-07", "amount": "-70,00", "description": "Ankauf"}])
        res = PayoutReconciler().reconcile(payouts, txs)
        self.assertEqual(res[0].status, PayoutStatus.UNMATCHED)

    def test_journal_schreiben(self):
        payouts = [Payout("PO1", date(2026, 6, 7), Decimal("104.40"))]
        txs = _bank([{"date": "2026-06-08", "amount": "104,40", "description": "eBay"}])
        res = PayoutReconciler().reconcile(payouts, txs)
        with tempfile.TemporaryDirectory() as d:
            pfad = os.path.join(d, "p.csv")
            n = schreibe_payout_journal(pfad, res)
            self.assertEqual(n, 1)
            with open(pfad, encoding="utf-8") as fh:
                inhalt = fh.read()
            self.assertIn("payout_id;status", inhalt)
            self.assertIn("matched", inhalt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
