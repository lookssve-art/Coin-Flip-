"""Tests fuer Lexware-Bankimport (CSV) und Lexware-Push (offline)."""

import os
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.imports import importiere_lexware_bank, lese_lexware_bank_csv
from src.integrations import LexwareSync
from src.models import Receipt
from src.review import ReviewQueue

_CSV = (
    "Buchungstag;Betrag;Verwendungszweck;Name\n"
    "03.06.2026;-70,00;Ankauf Karten;Privatverkaeufer\n"
    "05.06.2026;119,00;eBay Auszahlung;eBay\n"
)


def _receipt(rid, kategorie="buero", vorsteuer="ja"):
    return Receipt(id=rid, datum=date(2026, 6, 3), haendler="X",
                   brutto=Decimal("119"), netto=Decimal("100"),
                   ust_satz=Decimal("19"), ust_betrag=Decimal("19"),
                   kategorie=kategorie, vorsteuer_abzug=vorsteuer)


class TestLexwareBankCsv(unittest.TestCase):
    def _write(self, tmp, content=_CSV):
        p = os.path.join(tmp, "umsaetze.csv")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(content)
        return p

    def test_csv_normalisierung(self):
        with tempfile.TemporaryDirectory() as d:
            rows = lese_lexware_bank_csv(self._write(d))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["amount"], "-70,00")
            self.assertIn("Ankauf Karten", rows[0]["description"])

    def test_import_erzeugt_transaktionen(self):
        with tempfile.TemporaryDirectory() as d:
            txs = importiere_lexware_bank(self._write(d))
            self.assertEqual(len(txs), 2)
            self.assertEqual(txs[0].betrag, Decimal("-70.00"))
            self.assertEqual(txs[0].datum, date(2026, 6, 3))
            self.assertEqual(txs[1].betrag, Decimal("119.00"))

    def test_fehlende_spalten_meldet_fehler(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._write(d, "Foo;Bar\n1;2\n")
            with self.assertRaises(ValueError):
                lese_lexware_bank_csv(p)


class _FakeClient:
    def __init__(self):
        self.calls = []

    def erstelle_ausgabe_beleg(self, **kw):
        self.calls.append(kw)
        return {"id": f"voucher-{len(self.calls)}"}


class TestLexwareSync(unittest.TestCase):
    def test_push_nur_geeignete_belege(self):
        client = _FakeClient()
        q = ReviewQueue()
        q.add("Testgrund", bezug="B-REVIEW")
        sync = LexwareSync(client=client, review_queue=q,
                           kategorie_map={"buero": "uuid-buero"})
        receipts = [
            _receipt("B-OK", kategorie="buero", vorsteuer="ja"),
            _receipt("B-UNSICHER", kategorie="buero", vorsteuer="unsicher"),
            _receipt("B-NOCAT", kategorie="reise", vorsteuer="ja"),
            _receipt("B-REVIEW", kategorie="buero", vorsteuer="ja"),
        ]
        res = sync.push_belege(receipts)
        self.assertEqual(res.erstellt, ["B-OK"])
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]["kategorie_id"], "uuid-buero")
        gruende = {bid: g for bid, g in res.uebersprungen}
        self.assertIn("B-UNSICHER", gruende)
        self.assertIn("B-NOCAT", gruende)
        self.assertIn("B-REVIEW", gruende)


if __name__ == "__main__":
    unittest.main(verbosity=2)
