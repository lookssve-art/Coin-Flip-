"""Tests fuer den eBay-Finances-Client: Signatur-Header + Gebuehren-Aggregation."""

import os
import sys
import unittest
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.integrations import EbayFinanceClient, SigningContext

_SEED = bytes.fromhex("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb")

_TX = {
    "transactions": [
        {"transactionType": "SALE", "transactionId": "T1",
         "transactionDate": "2026-06-10T10:00:00.000Z",
         "amount": {"value": "104.55", "currency": "EUR"},
         "totalFeeAmount": {"value": "15.45", "currency": "EUR"},
         "buyer": {"country": "DE"}},
        {"transactionType": "SALE", "transactionId": "T2",
         "transactionDate": "2026-06-12T10:00:00.000Z",
         "amount": {"value": "40.00"}, "totalFeeAmount": {"value": "6.00"},
         "buyer": {"country": "FR"}},
        {"transactionType": "NON_SALE_CHARGE", "transactionId": "T3",
         "amount": {"value": "-2.50"}},
        {"transactionType": "REFUND", "transactionId": "T4",
         "amount": {"value": "10.00"}},
    ]
}


class TestSigningHeaders(unittest.TestCase):
    def test_request_wird_signiert(self):
        cap = {}
        def fake(url, headers=None, **kw):
            cap["url"] = url
            cap["headers"] = headers
            return _TX
        client = EbayFinanceClient(
            access_token="TOK",
            signing=SigningContext(jwe="JWE-XYZ", seed=_SEED, clock=lambda: 1700000000),
            _getter=fake,
        )
        txs = client.get_transactions(start=date(2026, 6, 1), end=date(2026, 6, 30))
        self.assertEqual(len(txs), 4)
        h = cap["headers"]
        self.assertEqual(h["Authorization"], "Bearer TOK")
        self.assertEqual(h["x-ebay-signature-key"], "JWE-XYZ")
        self.assertTrue(h["Signature"].startswith("sig1=:"))
        self.assertIn("created=1700000000", h["Signature-Input"])
        # Pfad in der Signatur enthaelt Query, Authority ist apiz.ebay.com.
        self.assertIn("/sell/finances/v1/transaction", cap["url"])

    def test_ohne_signing_keine_signaturheader(self):
        cap = {}
        def fake(url, headers=None, **kw):
            cap["headers"] = headers
            return _TX
        client = EbayFinanceClient(access_token="TOK", _getter=fake)
        client.get_transactions(start=date(2026, 6, 1), end=date(2026, 6, 30))
        self.assertNotIn("Signature", cap["headers"])
        self.assertNotIn("x-ebay-signature-key", cap["headers"])


class TestFeeSummary(unittest.TestCase):
    def test_aggregation(self):
        s = EbayFinanceClient.fee_summary(_TX["transactions"])
        # Gebuehren = 15.45 + 6.00 + |−2.50| = 23.95
        self.assertEqual(s["fees_total"], Decimal("23.95"))
        # Brutto = amount der SALE-Zeilen (Gebuehren sind davon einbehalten): 104.55 + 40.00
        self.assertEqual(s["sales_gross"], Decimal("144.55"))
        self.assertEqual(s["refunds_total"], Decimal("10.00"))
        self.assertEqual(s["n_sales"], 2)
        # ohne Werbe-Detail: werbung 0, gebuehren = fees_total
        self.assertEqual(s["werbung"], Decimal("0.00"))
        self.assertEqual(s["gebuehren"], Decimal("23.95"))

    def test_werbung_getrennt(self):
        txs = [
            {"transactionType": "SALE", "transactionId": "S1",
             "amount": {"value": "80.00"}, "totalFeeAmount": {"value": "20.00"},
             "orderLineItems": [{"marketplaceFees": [
                 {"feeType": "FINAL_VALUE_FEE", "amount": {"value": "14.00"}},
                 {"feeType": "AD_FEE", "amount": {"value": "6.00"}}]}]},
            {"transactionType": "NON_SALE_CHARGE", "transactionId": "N1",
             "feeType": "AD_FEE_PROMOTED_LISTINGS", "amount": {"value": "-3.00"}},
        ]
        s = EbayFinanceClient.fee_summary(txs)
        self.assertEqual(s["fees_total"], Decimal("23.00"))   # 20 + 3
        self.assertEqual(s["werbung"], Decimal("9.00"))       # 6 (AD_FEE) + 3 (NON_SALE ad)
        self.assertEqual(s["gebuehren"], Decimal("14.00"))    # Rest = Verkaufsgebuehr

    def test_versand_getrennt(self):
        txs = [
            {"transactionType": "SALE", "transactionId": "S1",
             "amount": {"value": "80.00"}, "totalFeeAmount": {"value": "12.00"}},
            {"transactionType": "SHIPPING_LABEL", "transactionId": "L1",
             "amount": {"value": "-4.90"}},
            {"transactionType": "NON_SALE_CHARGE", "transactionId": "N1",
             "feeType": "SHIPPING_LABEL_FEE", "amount": {"value": "-3.50"}},
        ]
        s = EbayFinanceClient.fee_summary(txs)
        # Versand NICHT in den Gebuehren
        self.assertEqual(s["versand"], Decimal("8.40"))       # 4.90 + 3.50
        self.assertEqual(s["fees_total"], Decimal("12.00"))   # nur Verkaufsgebuehr
        self.assertEqual(s["gebuehren"], Decimal("12.00"))

    def test_to_rows(self):
        rows = EbayFinanceClient.to_rows(_TX["transactions"])
        # NON_SALE_CHARGE wird uebersprungen -> nur 2 SALE + 1 REFUND = 3 Zeilen.
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["gross"], "104.55")
        self.assertEqual(rows[0]["fees"], "15.45")
        self.assertEqual(rows[1]["buyer_country"], "FR")
        self.assertEqual(rows[2]["refund"], "10.00")
        # keine Phantom-Gebuehrenzeile aus der NON_SALE_CHARGE
        self.assertFalse(any(r.get("_review") for r in rows))


if __name__ == "__main__":
    unittest.main(verbosity=2)
