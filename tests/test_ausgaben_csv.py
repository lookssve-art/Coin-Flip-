"""Tests fuer den manuellen Ausgaben-CSV-Import (echte Rechnungen)."""

import os
import sys
import tempfile
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.imports import lese_ausgaben_csv


def _schreibe(text: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


class TestAusgabenCsv(unittest.TestCase):
    def test_semikolon_und_kommazahl(self):
        path = _schreibe(
            "datum;kategorie;betrag;beschreibung\n"
            "2026-06-10;versand;4,90;DHL Paket\n"
            "2026-06-12;buero;19,99;Druckerpapier\n"
        )
        try:
            receipts = lese_ausgaben_csv(path)
        finally:
            os.remove(path)
        self.assertEqual(len(receipts), 2)
        self.assertEqual(receipts[0].brutto, Decimal("4.90"))
        self.assertEqual(receipts[0].kategorie, "versand")
        self.assertEqual(receipts[0].vorsteuer_abzug, "nein")
        self.assertEqual(receipts[1].brutto, Decimal("19.99"))

    def test_tausenderpunkt_mit_kommazahl(self):
        path = _schreibe(
            "datum;kategorie;betrag;beschreibung\n"
            "2026-06-01;wareneinkauf;1.234,56;Sammelposten\n"
        )
        try:
            receipts = lese_ausgaben_csv(path)
        finally:
            os.remove(path)
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0].brutto, Decimal("1234.56"))

    def test_komma_delimiter_punktdezimal(self):
        path = _schreibe(
            "datum,kategorie,betrag,beschreibung\n"
            "2026-06-01,software,12.50,Tool-Abo\n"
        )
        try:
            receipts = lese_ausgaben_csv(path)
        finally:
            os.remove(path)
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0].brutto, Decimal("12.50"))

    def test_leere_und_ungueltige_zeilen_uebersprungen(self):
        path = _schreibe(
            "datum;kategorie;betrag;beschreibung\n"
            "2026-06-10;versand;;ohne betrag\n"
            "2026-06-11;versand;0;null betrag\n"
            "2026-06-12;versand;5,00;ok\n"
        )
        try:
            receipts = lese_ausgaben_csv(path)
        finally:
            os.remove(path)
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0].brutto, Decimal("5.00"))

    def test_fehlende_datei_leer(self):
        self.assertEqual(lese_ausgaben_csv("/nope/does/not/exist.csv"), [])
        self.assertEqual(lese_ausgaben_csv(""), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
