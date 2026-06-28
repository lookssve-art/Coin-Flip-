"""Tests fuer die Beleg-/OCR-Pipeline (MVP-Punkt 3, offline)."""

import os
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ocr import extrahiere_felder, RuleBasedClassifier, BelegPipeline
from src.ocr.pipeline import OcrErgebnis
from src.review import ReviewQueue
from src.storage import ReceiptStore

_BON = """REWE Markt GmbH
Bahnhofstr. 1, 80331 Muenchen
Datum 03.06.2026
Toner Drucker
Summe 119,00
MwSt 19% 19,00
"""


class TestExtraktion(unittest.TestCase):
    def test_felder_aus_bon(self):
        r = extrahiere_felder(_BON)
        self.assertEqual(r.datum, date(2026, 6, 3))
        self.assertEqual(r.brutto, Decimal("119,00".replace(",", ".")))
        self.assertEqual(r.ust_satz, Decimal("19"))
        self.assertEqual(r.netto, Decimal("100.00"))
        self.assertEqual(r.ust_betrag, Decimal("19.00"))
        self.assertGreaterEqual(r.confidence, 0.99)

    def test_unvollstaendig_senkt_confidence(self):
        r = extrahiere_felder("Irgendein Text ohne Betraege")
        self.assertLess(r.confidence, 0.5)
        self.assertIn("brutto", r.fehlend)


class TestRuleClassifier(unittest.TestCase):
    def test_buero_vorsteuer_ja(self):
        k = RuleBasedClassifier().classify("Toner Drucker Papier", haendler="Buerobedarf")
        self.assertEqual(k.kategorie, "buero")
        self.assertEqual(k.vorsteuer_abzug, "ja")

    def test_unbekannt_unsicher(self):
        k = RuleBasedClassifier().classify("xyz", haendler="")
        self.assertEqual(k.kategorie, "sonstiges")
        self.assertEqual(k.vorsteuer_abzug, "unsicher")


class TestPipeline(unittest.TestCase):
    def _pipeline(self, tmp, ocr_text, ocr_conf):
        return BelegPipeline(
            store=ReceiptStore(tmp),
            review_queue=ReviewQueue(),
            ocr=lambda content, mime: OcrErgebnis(text=ocr_text, confidence=ocr_conf),
        )

    def test_guter_bon_kein_review(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._pipeline(d, _BON, ocr_conf=0.95)
            receipt = p.verarbeite(b"%PNG fake bild", mime="image/png")
            self.assertEqual(receipt.kategorie, "buero")
            self.assertEqual(receipt.vorsteuer_abzug, "ja")
            self.assertEqual(receipt.ust_satz, Decimal("19"))
            self.assertIsNotNone(receipt.archived_hash)
            self.assertEqual(len(p.review_queue.offen()), 0)

    def test_schlechte_ocr_geht_in_review(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._pipeline(d, "unleserlich", ocr_conf=0.2)
            p.verarbeite(b"%PDF schlecht", mime="application/pdf")
            self.assertGreater(len(p.review_queue.offen()), 0)

    def test_original_wird_archiviert(self):
        with tempfile.TemporaryDirectory() as d:
            store = ReceiptStore(d)
            p = BelegPipeline(store=store, review_queue=ReviewQueue(),
                              ocr=lambda c, m: OcrErgebnis(_BON, 0.95))
            receipt = p.verarbeite(b"%PNG bild", mime="image/png")
            self.assertTrue(store.verify(receipt.archived_hash, ".png"))

    def test_xrechnung_wird_strukturiert_verbucht(self):
        xml = b"""<?xml version="1.0"?>
        <Invoice xmlns="urn:oasis:names:tc:ubl">
          <ID>RE-2026-007</ID>
          <IssueDate>2026-06-01</IssueDate>
          <RegistrationName>Grosshandel TCG GmbH</RegistrationName>
          <PayableAmount>119.00</PayableAmount>
          <TaxAmount>19.00</TaxAmount>
        </Invoice>"""
        with tempfile.TemporaryDirectory() as d:
            p = BelegPipeline(store=ReceiptStore(d), review_queue=ReviewQueue())
            receipt = p.verarbeite(xml, mime="application/xml")
            self.assertEqual(receipt.brutto, Decimal("119.00"))
            self.assertEqual(receipt.ust_betrag, Decimal("19.00"))
            self.assertEqual(receipt.ust_satz, Decimal("19"))
            self.assertEqual(receipt.datum, date(2026, 6, 1))   # IssueDate, nicht heute
            self.assertEqual(receipt.ocr_confidence, 1.0)  # strukturiert, kein OCR-Risiko


if __name__ == "__main__":
    unittest.main(verbosity=2)
