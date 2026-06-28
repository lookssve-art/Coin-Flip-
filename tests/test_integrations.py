"""Tests fuer eBay OAuth + Finances (offline, injizierter HTTP)."""

import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.integrations import EbayOAuth, EbayFinanceClient
from src.imports import importiere_ebay_verkaeufe
from src.models import TaxScheme


class TestEbayOAuth(unittest.TestCase):
    def _oauth(self, capture):
        def fake_poster(url, form, headers=None, timeout=30.0):
            capture["url"] = url
            capture["form"] = form
            capture["headers"] = headers
            if form.get("grant_type") == "authorization_code":
                return {"access_token": "AC", "expires_in": 7200,
                        "refresh_token": "RT", "refresh_token_expires_in": 47304000}
            return {"access_token": "AC2", "expires_in": 7200}
        return EbayOAuth(app_id="APP", cert_id="SECRET", ru_name="My-RuName",
                         _poster=fake_poster)

    def test_consent_url_enthaelt_parameter(self):
        url = self._oauth({}).consent_url(state="sero")
        self.assertIn("auth.ebay.com/oauth2/authorize", url)
        self.assertIn("client_id=APP", url)
        self.assertIn("redirect_uri=My-RuName", url)
        self.assertIn("response_type=code", url)
        self.assertIn("state=sero", url)
        self.assertIn("sell.finances", url)

    def test_exchange_code_liefert_refresh_token(self):
        cap = {}
        tok = self._oauth(cap).exchange_code("THECODE")
        self.assertEqual(tok.access_token, "AC")
        self.assertEqual(tok.refresh_token, "RT")
        self.assertEqual(cap["form"]["grant_type"], "authorization_code")
        self.assertEqual(cap["form"]["code"], "THECODE")
        self.assertTrue(cap["headers"]["Authorization"].startswith("Basic "))

    def test_refresh_nutzt_refresh_grant(self):
        cap = {}
        tok = self._oauth(cap).refresh("RT")
        self.assertEqual(tok.access_token, "AC2")
        self.assertEqual(cap["form"]["grant_type"], "refresh_token")
        self.assertEqual(cap["form"]["refresh_token"], "RT")


class TestEbayFinance(unittest.TestCase):
    def test_get_transactions_baut_filter_und_header(self):
        cap = {}
        def fake_getter(url, headers=None, **kw):
            cap["url"] = url
            cap["headers"] = headers
            return {"transactions": [{"transactionType": "SALE"}]}
        client = EbayFinanceClient(access_token="AC", _getter=fake_getter)
        txns = client.get_transactions(start=date(2026, 6, 1), end=date(2026, 6, 30))
        self.assertEqual(len(txns), 1)
        self.assertIn("transactionDate", cap["url"])
        self.assertEqual(cap["headers"]["Authorization"], "Bearer AC")
        self.assertEqual(cap["headers"]["X-EBAY-C-MARKETPLACE-ID"], "EBAY_DE")

    def test_to_rows_mapping(self):
        txns = [
            {"transactionId": "T1", "transactionType": "SALE", "transactionDate": "2026-06-03T10:00:00.000Z",
             "amount": {"value": "120.00"}, "totalFeeAmount": {"value": "15.60"},
             "buyer": {"country": "FR"}},
            {"transactionId": "T2", "transactionType": "REFUND", "transactionDate": "2026-06-05T09:00:00.000Z",
             "amount": {"value": "20.00"}},
            {"transactionId": "T3", "transactionType": "NON_SALE_CHARGE",
             "transactionDate": "2026-06-06T09:00:00.000Z", "amount": {"value": "5.00"}},
        ]
        rows = EbayFinanceClient.to_rows(txns)
        # Mapping in das Importer-Schema und weiter zu PlatformSale.
        sales = importiere_ebay_verkaeufe(rows)
        self.assertEqual(sales[0].brutto, __import__("decimal").Decimal("120.00"))
        self.assertEqual(sales[0].gebuehren, __import__("decimal").Decimal("15.60"))
        self.assertEqual(sales[0].customer_country, "FR")
        self.assertEqual(sales[1].refund, __import__("decimal").Decimal("20.00"))
        self.assertTrue(any(r.get("_review") for r in rows))  # NON_SALE_CHARGE markiert


if __name__ == "__main__":
    unittest.main(verbosity=2)
