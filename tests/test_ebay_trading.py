"""Tests fuer den eBay-Trading-API-Kaeufe-Client (XML-Parsing, offline)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.integrations import EbayTradingClient, parse_buyer_orders, parse_seller_orders

_XML = """<?xml version="1.0" encoding="UTF-8"?>
<GetOrdersResponse xmlns="urn:ebay:apis:eBLBaseComponents">
  <Ack>Success</Ack>
  <OrderArray>
    <Order>
      <CreatedTime>2026-06-10T12:00:00.000Z</CreatedTime>
      <TransactionArray>
        <Transaction>
          <Item><ItemID>112233</ItemID><SKU>CHARIZARD-PSA10</SKU></Item>
          <TransactionPrice currencyID="EUR">70.00</TransactionPrice>
        </Transaction>
        <Transaction>
          <Item><ItemID>445566</ItemID></Item>
          <TransactionPrice currencyID="EUR">25.50</TransactionPrice>
        </Transaction>
      </TransactionArray>
    </Order>
  </OrderArray>
</GetOrdersResponse>"""


class TestParseBuyerOrders(unittest.TestCase):
    def test_parsing_sku_und_itemid(self):
        rows = parse_buyer_orders(_XML)
        self.assertEqual(len(rows), 2)
        # SKU hat Vorrang vor ItemID als product_id
        self.assertEqual(rows[0]["product_id"], "CHARIZARD-PSA10")
        self.assertEqual(rows[0]["date"], "2026-06-10")
        self.assertEqual(rows[0]["price"], "70.00")
        # ohne SKU -> ItemID
        self.assertEqual(rows[1]["product_id"], "445566")

    def test_kaputtes_xml_leer(self):
        self.assertEqual(parse_buyer_orders("<nope"), [])


_SELLER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<GetOrdersResponse xmlns="urn:ebay:apis:eBLBaseComponents">
  <OrderArray>
    <Order>
      <OrderID>ORD-1</OrderID>
      <CreatedTime>2026-06-12T09:00:00.000Z</CreatedTime>
      <ShippingAddress><Country>FR</Country></ShippingAddress>
      <TransactionArray>
        <Transaction>
          <TransactionID>T1</TransactionID>
          <Item><ItemID>999</ItemID><SKU>CHARIZARD-PSA10</SKU></Item>
          <TransactionPrice currencyID="EUR">120.00</TransactionPrice>
          <QuantityPurchased>1</QuantityPurchased>
        </Transaction>
      </TransactionArray>
    </Order>
  </OrderArray>
</GetOrdersResponse>"""


class TestParseSellerOrders(unittest.TestCase):
    def test_verkaufszeilen(self):
        from decimal import Decimal
        from src.imports import importiere_ebay_verkaeufe
        rows = parse_seller_orders(_SELLER_XML, default_tax_scheme="differenz")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["product_id"], "CHARIZARD-PSA10")
        self.assertEqual(rows[0]["gross"], "120.00")
        self.assertEqual(rows[0]["buyer_country"], "FR")
        self.assertEqual(rows[0]["tax_scheme"], "differenz")
        # geht sauber durch den Importer
        sales = importiere_ebay_verkaeufe(rows)
        self.assertEqual(sales[0].brutto, Decimal("120.00"))
        self.assertEqual(sales[0].customer_country, "FR")

    def test_menge_multipliziert(self):
        xml = _SELLER_XML.replace("<QuantityPurchased>1", "<QuantityPurchased>3")
        rows = parse_seller_orders(xml)
        self.assertEqual(rows[0]["gross"], "360.00")


class TestTradingClient(unittest.TestCase):
    def test_header_und_zeitfenster(self):
        cap = {}
        def fake(url, method=None, body=None, headers=None, **kw):
            cap["url"] = url
            cap["headers"] = headers
            cap["body"] = body.decode("utf-8")
            return _XML
        client = EbayTradingClient(access_token="TOK", _sender=fake)
        rows = client.get_buyer_purchases(tage=200)   # wird auf 90 begrenzt
        self.assertEqual(len(rows), 2)
        self.assertEqual(cap["headers"]["X-EBAY-API-CALL-NAME"], "GetOrders")
        self.assertEqual(cap["headers"]["X-EBAY-API-IAF-TOKEN"], "TOK")
        self.assertIn("<OrderRole>Buyer</OrderRole>", cap["body"])
        self.assertIn("CreateTimeFrom", cap["body"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
