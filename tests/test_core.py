"""Tests fuer das Compliance-Fundament (stdlib unittest -> ohne pytest lauffaehig)."""

import os
import sys
import tempfile
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.audit import AuditLog
from src.storage import ReceiptStore
from src.tax import einzeldifferenz, gesamtdifferenz, SchwellenMonitor, ustva_vorbereitung
from src.einvoice import erkenne_format, parse_xrechnung
from src.models import EInvoiceFormat
from src.review import ReviewQueue, pruefe_review_trigger
from src.verfahrensdoku import generiere_verfahrensdoku


class TestDifferenzbesteuerung(unittest.TestCase):
    def test_einzeldifferenz_marge_und_ust(self):
        r = einzeldifferenz(Decimal("120"), Decimal("70"), Decimal("19"))
        self.assertEqual(r.marge, Decimal("50.00"))
        # USt in der 50-EUR-Marge: 50 / 1.19 = 42.02 netto, 7.98 USt
        self.assertEqual(r.netto_marge, Decimal("42.02"))
        self.assertEqual(r.ust_betrag, Decimal("7.98"))

    def test_verlust_keine_negative_ust(self):
        r = einzeldifferenz(Decimal("50"), Decimal("80"))
        self.assertEqual(r.marge, Decimal("0"))
        self.assertEqual(r.ust_betrag, Decimal("0"))

    def test_gesamtdifferenz_schliesst_posten_ueber_750_aus(self):
        r = gesamtdifferenz([(Decimal("100"), Decimal("60")),
                             (Decimal("900"), Decimal("400"))])
        # Nur der erste Posten zaehlt (zweiter > 750).
        self.assertEqual(r.marge, Decimal("40.00"))
        self.assertIn("750", r.hinweis)


class TestSchwellen(unittest.TestCase):
    def test_fruehwarnung_ab_80_prozent(self):
        mon = SchwellenMonitor(warnung_ab_prozent=Decimal("80"))
        s = mon.kleinunternehmer_laufend(Decimal("85000"))
        self.assertTrue(s.warnung)
        self.assertFalse(s.ueberschritten)

    def test_ueberschreitung(self):
        mon = SchwellenMonitor()
        s = mon.oss_fernverkauf(Decimal("12000"))
        self.assertTrue(s.ueberschritten)


class TestUStVa(unittest.TestCase):
    def test_kleinunternehmer_keine_zahllast(self):
        r = ustva_vorbereitung("Q2/2026", kleinunternehmer=True,
                               umsatzsteuer_je_satz={"19": Decimal("100")})
        self.assertEqual(r.zahllast, Decimal("0"))
        self.assertTrue(any("§ 19" in h for h in r.hinweise))

    def test_regelbesteuerung_zahllast(self):
        r = ustva_vorbereitung("Q2/2026", kleinunternehmer=False,
                               umsatzsteuer_je_satz={"19": Decimal("190")},
                               vorsteuer=Decimal("40"))
        self.assertEqual(r.zahllast, Decimal("150.00"))
        self.assertTrue(r.ist_entwurf)


class TestAuditLog(unittest.TestCase):
    def test_append_und_verify(self):
        with tempfile.TemporaryDirectory() as d:
            log = AuditLog(os.path.join(d, "audit.jsonl"))
            log.append("a", {"x": 1})
            log.append("b", {"y": 2})
            ok, fehler = log.verify()
            self.assertTrue(ok)
            self.assertIsNone(fehler)
            self.assertEqual(log.count(), 2)

    def test_manipulation_bricht_kette(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "audit.jsonl")
            log = AuditLog(path)
            log.append("a", {"x": 1})
            log.append("b", {"y": 2})
            with open(path, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
            lines[0] = lines[0].replace('"x": 1', '"x": 999')
            with open(path, "w", encoding="utf-8") as fh:
                fh.writelines(lines)
            ok, fehler = log.verify()
            self.assertFalse(ok)
            self.assertEqual(fehler, 1)


class TestReceiptStore(unittest.TestCase):
    def test_wormablage_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            store = ReceiptStore(d)
            o1 = store.store(b"rechnung-xml", ".xml")
            o2 = store.store(b"rechnung-xml", ".xml")
            self.assertEqual(o1.sha256, o2.sha256)
            self.assertFalse(o1.bereits_vorhanden)
            self.assertTrue(o2.bereits_vorhanden)
            self.assertTrue(store.verify(o1.sha256, ".xml"))


class TestEInvoice(unittest.TestCase):
    def test_pdf_ohne_datensatz_ist_keine_erechnung(self):
        self.assertEqual(erkenne_format(b"%PDF-1.7\n...kein xml..."),
                         EInvoiceFormat.SONSTIGE)

    def test_xrechnung_erkennung_und_parsing(self):
        xml = b"""<?xml version="1.0"?>
        <Invoice xmlns="urn:oasis:names:tc:ubl">
          <ID>RE-2026-001</ID>
          <IssueDate>2026-06-01</IssueDate>
          <PayableAmount>119.00</PayableAmount>
          <TaxAmount>19.00</TaxAmount>
        </Invoice>"""
        self.assertEqual(erkenne_format(xml), EInvoiceFormat.XRECHNUNG)
        res = parse_xrechnung(xml)
        self.assertTrue(res.valid)
        self.assertEqual(res.felder["rechnungsnummer"], "RE-2026-001")
        self.assertEqual(res.felder["betrag_brutto"], Decimal("119.00"))

    def test_fehlende_pflichtfelder_review(self):
        xml = b"<Invoice><ID></ID></Invoice>"
        res = parse_xrechnung(xml)
        self.assertFalse(res.valid)
        self.assertTrue(res.review_required)


class TestReviewQueue(unittest.TestCase):
    def test_trigger_und_blockade(self):
        gruende = pruefe_review_trigger(import_einfuhrumsatzsteuer=True,
                                        betrag_brutto=Decimal("3000"),
                                        betragsschwelle=Decimal("2000"))
        self.assertEqual(len(gruende), 2)
        q = ReviewQueue()
        q.add_many(gruende, bezug="vorgang-1")
        self.assertTrue(q.hat_offene("vorgang-1"))
        item = q.offen()[0]
        q.aufloesen(item.id, freigeben=True, von="steuerberater")
        self.assertEqual(len(q.offen()), 1)  # zweiter Fall noch offen


class TestVerfahrensdoku(unittest.TestCase):
    def test_generierung_enthaelt_kernpunkte(self):
        cfg = {"unternehmen": {"name": "SERO"}, "steuer": {"kleinunternehmer": True},
               "aufbewahrung": {}, "pfade": {}}
        md = generiere_verfahrensdoku(cfg)
        self.assertIn("Verfahrensdokumentation", md)
        self.assertIn("GoBD", md)
        self.assertIn("SERO", md)


if __name__ == "__main__":
    unittest.main(verbosity=2)
