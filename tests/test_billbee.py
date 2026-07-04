"""Tests fuer den Billbee-Connector (Order-Parsing, Auth-Header, Pagination)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.integrations import BillbeeClient, parse_billbee_orders

_ORDERS = {
    "Paging": {"Page": 1, "TotalPages": 1},
    "Data": [
        {
            "OrderNumber": "eBay-123",
            "CreatedAt": "2026-06-10T12:00:00",
            "TotalCost": 120.00,
            "OrderItems": [
                {"Product": {"Title": "Charizard PSA 10", "SKU": "CHAR-1"},
                 "Quantity": 1, "TotalPrice": 120.00},
            ],
            "ShippingAddress": {"FirstName": "Max", "LastName": "Muster",
                                "Street": "Marktweg 3", "Zip": "50667",
                                "City": "Köln", "CountryCode": "DE"},
        },
        {
            "BillBeeOrderId": 999,
            "CreatedAt": "2026-06-12T09:00:00",
            "OrderItems": [
                {"Product": {"Title": "Booster A"}, "Quantity": 2, "TotalPrice": 9.00},
                {"Product": {"Title": "Booster B"}, "Quantity": 1, "TotalPrice": 5.00},
            ],
            "ShippingAddress": {"Name": "Anna", "CountryCode": "FR"},
        },
    ],
}


class TestParseBillbee(unittest.TestCase):
    def test_eine_zeile_pro_bestellung(self):
        rows = parse_billbee_orders(_ORDERS, default_tax_scheme="differenz")
        self.assertEqual(len(rows), 2)

    def test_felder_bestellung1(self):
        r = parse_billbee_orders(_ORDERS)[0]
        self.assertEqual(r["id"], "eBay-123")
        self.assertEqual(r["date"], "2026-06-10")
        self.assertEqual(r["gross"], "120.00")
        self.assertEqual(r["title"], "Charizard PSA 10")
        self.assertEqual(r["buyer_name"], "Max Muster")
        self.assertEqual(r["buyer_city"], "Köln")
        self.assertEqual(r["buyer_country"], "DE")
        self.assertEqual(r["tax_scheme"], "differenz")

    def test_gross_aus_items_wenn_kein_totalcost(self):
        r = parse_billbee_orders(_ORDERS)[1]
        # kein TotalCost -> Summe der Positionen 9 + 5 = 14
        self.assertEqual(r["gross"], "14.00")
        self.assertEqual(r["quantity"], "3")
        self.assertIn("Booster A", r["title"])
        self.assertEqual(r["buyer_country"], "FR")

    def test_geht_durch_den_importer(self):
        from decimal import Decimal
        from src.imports import importiere_ebay_verkaeufe
        sales = importiere_ebay_verkaeufe(parse_billbee_orders(_ORDERS))
        self.assertEqual(sales[0].brutto, Decimal("120.00"))
        self.assertEqual(sales[0].customer_country, "DE")

    def test_leer_und_kaputt(self):
        self.assertEqual(parse_billbee_orders({}), [])
        self.assertEqual(parse_billbee_orders({"Data": "nope"}), [])


class TestBillbeeClient(unittest.TestCase):
    def test_auth_header_und_query(self):
        cap = {}
        def fake(url, headers=None, **kw):
            cap["url"] = url
            cap["headers"] = headers
            return _ORDERS
        client = BillbeeClient(api_key="K", user="u@x.de", api_password="pw", _getter=fake)
        rows = client.alle_bestellungen(von="2026-06-01")
        self.assertEqual(len(rows), 2)
        self.assertEqual(cap["headers"]["X-Billbee-Api-Key"], "K")
        self.assertTrue(cap["headers"]["Authorization"].startswith("Basic "))
        self.assertIn("minOrderDate=2026-06-01", cap["url"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
