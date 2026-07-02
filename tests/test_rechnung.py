"""Tests fuer das Rechnungsmodul: Nummern, Generator, Register, Lexware-Mapping."""

import os
import sys
import tempfile
import unittest
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rechnung import (Absender, Nummernkreis, RechnungsRegister,
                          rechnung_aus_verkauf, render_html, render_text)
from src.integrations import rechnung_zu_lexware, LexwareInvoiceClient


@dataclass
class _Sale:
    id: str
    datum: date
    brutto: Decimal
    product_id: str = "Artikel-X"
    product_name: str = ""
    menge: Decimal = Decimal("1")
    einzelpreis: Decimal = Decimal("0")
    customer_country: str = "DE"
    customer_name: str = ""


def _absender() -> Absender:
    return Absender(name="SERO Handel", strasse="Hauptstr. 1", plz="80331",
                    ort="München", steuernummer="143/123/45678", iban="DE12...")


class TestNummernkreis(unittest.TestCase):
    def test_fortlaufend_mit_jahr(self):
        fd, p = tempfile.mkstemp(suffix=".json"); os.close(fd); os.remove(p)
        nk = Nummernkreis(pfad=p, prefix="", mit_jahr=True, start=1)
        try:
            self.assertEqual(nk.naechste(2026), "2026-0001")
            self.assertEqual(nk.naechste(2026), "2026-0002")
            # Vorschau erhoeht den Zaehler nicht.
            self.assertEqual(nk.vorschau(2026), "2026-0003")
            self.assertEqual(nk.naechste(2026), "2026-0003")
            # Jahreswechsel beginnt neu.
            self.assertEqual(nk.naechste(2027), "2027-0001")
        finally:
            os.path.exists(p) and os.remove(p)

    def test_prefix_und_ohne_jahr(self):
        fd, p = tempfile.mkstemp(suffix=".json"); os.close(fd); os.remove(p)
        nk = Nummernkreis(pfad=p, prefix="RE-", mit_jahr=False, start=1001)
        try:
            self.assertEqual(nk.naechste(2026), "RE-1001")
            self.assertEqual(nk.naechste(2026), "RE-1002")
        finally:
            os.path.exists(p) and os.remove(p)

    def test_persistenz_ueber_instanzen(self):
        fd, p = tempfile.mkstemp(suffix=".json"); os.close(fd); os.remove(p)
        try:
            self.assertEqual(Nummernkreis(pfad=p).naechste(2026), "2026-0001")
            # Neue Instanz liest den Stand und macht weiter.
            self.assertEqual(Nummernkreis(pfad=p).naechste(2026), "2026-0002")
        finally:
            os.path.exists(p) and os.remove(p)


class TestGenerator(unittest.TestCase):
    def test_rechnung_aus_verkauf(self):
        s = _Sale("ORD-1", date(2026, 6, 10), Decimal("200.00"),
                  product_id="Charizard PSA10", customer_country="FR")
        r = rechnung_aus_verkauf(s, nummer="2026-0001", absender=_absender())
        self.assertEqual(r.nummer, "2026-0001")
        self.assertEqual(r.summe, Decimal("200.00"))
        self.assertEqual(r.positionen[0].bezeichnung, "Charizard PSA10")
        self.assertEqual(r.bestell_referenz, "ORD-1")
        self.assertTrue(r.kleinunternehmer)
        self.assertEqual(r.empfaenger.land, "FR")

    def test_stueckzahl_und_einzelpreis(self):
        s = _Sale("ORD-9", date(2026, 6, 10), Decimal("13.50"),
                  product_name="Booster Pack", menge=Decimal("3"),
                  einzelpreis=Decimal("4.50"))
        r = rechnung_aus_verkauf(s, nummer="2026-0009", absender=_absender())
        p = r.positionen[0]
        self.assertEqual(p.menge, Decimal("3"))
        self.assertEqual(p.einzelpreis, Decimal("4.50"))
        self.assertEqual(p.gesamt, Decimal("13.50"))
        self.assertEqual(r.summe, Decimal("13.50"))

    def test_einzelpreis_faellt_auf_brutto_durch_menge(self):
        # ohne expliziten Einzelpreis: aus brutto/menge ableiten
        s = _Sale("ORD-8", date(2026, 6, 10), Decimal("30.00"), menge=Decimal("2"))
        r = rechnung_aus_verkauf(s, nummer="2026-0008", absender=_absender())
        p = r.positionen[0]
        self.assertEqual(p.einzelpreis, Decimal("15.00"))
        self.assertEqual(p.gesamt, Decimal("30.00"))

    def test_summe_stimmt_bei_unteilbarer_menge(self):
        # brutto/menge nicht cent-glatt (10.00/3) -> Summe MUSS = brutto bleiben,
        # nicht 9.99 (Rundungsverlust). Wird zur Sammelposition.
        s = _Sale("ORD-7", date(2026, 6, 10), Decimal("10.00"), menge=Decimal("3"))
        r = rechnung_aus_verkauf(s, nummer="2026-0007", absender=_absender())
        self.assertEqual(r.summe, Decimal("10.00"))

    def test_artikeltitel_bevorzugt_vor_itemid(self):
        s = _Sale("ORD-1", date(2026, 6, 10), Decimal("3.00"),
                  product_id="227357704604", product_name="Pokemon Charizard Holo")
        r = rechnung_aus_verkauf(s, nummer="2026-0001", absender=_absender())
        self.assertEqual(r.positionen[0].bezeichnung, "Pokemon Charizard Holo")

    def test_render_enthaelt_pflichtangaben(self):
        s = _Sale("ORD-1", date(2026, 6, 10), Decimal("200.00"))
        r = rechnung_aus_verkauf(s, nummer="2026-0001", absender=_absender())
        txt = render_text(r)
        self.assertIn("Rechnung 2026-0001", txt)
        self.assertIn("§ 19 UStG", txt)
        self.assertIn("143/123/45678", txt)
        h = render_html(r)
        self.assertIn("2026-0001", h)
        self.assertIn("200.00", h)
        self.assertIn("§ 19 UStG", h)

    def test_html_escaped(self):
        s = _Sale("ORD-1", date(2026, 6, 10), Decimal("5.00"),
                  product_id="<script>alert(1)</script>")
        r = rechnung_aus_verkauf(s, nummer="2026-0001", absender=_absender())
        h = render_html(r)
        self.assertNotIn("<script>alert(1)</script>", h)
        self.assertIn("&lt;script&gt;", h)


class TestRegister(unittest.TestCase):
    def test_idempotenz(self):
        fd, p = tempfile.mkstemp(suffix=".json"); os.close(fd); os.remove(p)
        try:
            reg = RechnungsRegister(pfad=p)
            self.assertFalse(reg.hat("ORD-1"))
            reg.merke("ORD-1", "2026-0001", datei="x.html")
            self.assertTrue(reg.hat("ORD-1"))
            self.assertEqual(reg.eintrag("ORD-1")["nummer"], "2026-0001")
            # offene_lexware: noch nicht gepusht
            self.assertEqual(reg.offene_lexware(), ["ORD-1"])
            reg.merke("ORD-1", "2026-0001", lexware_id="lex-123")
            self.assertEqual(reg.offene_lexware(), [])
            # Persistenz
            self.assertTrue(RechnungsRegister(pfad=p).hat("ORD-1"))
        finally:
            os.path.exists(p) and os.remove(p)


class TestLexwareMapping(unittest.TestCase):
    def test_kleinunternehmer_vatfree(self):
        s = _Sale("ORD-1", date(2026, 6, 10), Decimal("200.00"),
                  product_id="Charizard")
        r = rechnung_aus_verkauf(s, nummer="2026-0001", absender=_absender())
        body = rechnung_zu_lexware(r)
        self.assertEqual(body["taxConditions"]["taxType"], "vatfree")
        self.assertIn("§ 19 UStG", body["taxConditions"]["taxTypeNote"])
        li = body["lineItems"][0]
        self.assertEqual(li["unitPrice"]["netAmount"], 200.0)
        self.assertEqual(li["unitPrice"]["taxRatePercentage"], 0)
        self.assertEqual(li["name"], "Charizard")
        self.assertIn("eBay-Bestellung: ORD-1", body["remark"])

    def test_client_post_und_finalize(self):
        cap = {}
        def fake(url, method=None, payload=None, headers=None, **kw):
            cap["url"] = url; cap["method"] = method; cap["payload"] = payload
            return {"id": "lex-abc", "resourceUri": "..."}
        s = _Sale("ORD-1", date(2026, 6, 10), Decimal("50.00"))
        r = rechnung_aus_verkauf(s, nummer="2026-0001", absender=_absender())
        client = LexwareInvoiceClient(api_key="KEY", _poster=fake)
        res = client.rechnung_anlegen(r, finalize=True)
        self.assertEqual(res["id"], "lex-abc")
        self.assertTrue(cap["url"].endswith("/invoices?finalize=true"))
        self.assertEqual(cap["method"], "POST")

    def test_pdf_zweistufig(self):
        calls = []
        def fake_json(url, headers=None, **kw):
            calls.append(url)
            return {"documentFileId": "file-9"}
        def fake_bytes(url, headers=None, **kw):
            calls.append(url)
            return b"%PDF-1.7 fake"
        client = LexwareInvoiceClient(api_key="KEY", _poster=fake_json, _bytes=fake_bytes)
        pdf = client.pdf_laden("lex-abc")
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn("/invoices/lex-abc/document", calls[0])
        self.assertIn("/files/file-9", calls[1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
