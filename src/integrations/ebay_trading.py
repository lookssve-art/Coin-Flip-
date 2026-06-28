"""eBay Trading API (Legacy XML) — eigene Kaeufe lesen (GetOrders, OrderRole=Buyer).

Die modernen Buy-APIs geben die persoenliche Kaufhistorie NICHT her. Der dokumentierte
Weg ist die alte Trading-API ``GetOrders`` mit ``OrderRole=Buyer`` — sie liefert die
Bestellungen, in denen der authentifizierte Nutzer der **Kaeufer** war.

WICHTIGE GRENZE: eBay liefert hier nur etwa die **letzten 90 Tage**. Aeltere Kaeufe
(z. B. fuer Altbestaende, die schon vor Monaten gekauft wurden) muessen ueber den
Bestellverlauf-Export von der eBay-Website kommen.

Authentifizierung: OAuth-Access-Token im Header ``X-EBAY-API-IAF-TOKEN``. Falls eBay
mit Auth-Fehler antwortet, muss der Consent ggf. mit passendem Scope erneuert werden.
Der HTTP-Sender ist injizierbar -> offline testbar (XML-Parsing ohne Netzwerk).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Callable

from ..util.http import http_text

_TRADING_URL = {
    "production": "https://api.ebay.com/ws/api.dll",
    "sandbox": "https://api.sandbox.ebay.com/ws/api.dll",
}
_SITEID_DE = "77"
_COMPAT_LEVEL = "1207"
_NS = "urn:ebay:apis:eBLBaseComponents"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find(el, name):
    for sub in el.iter():
        if _local(sub.tag) == name:
            return sub
    return None


def parse_buyer_orders(xml: str) -> list[dict]:
    """Extrahiert Kaufzeilen aus einer GetOrders-Antwort (OrderRole=Buyer).

    Rueckgabe: Liste von {product_id, date, price} — kompatibel mit
    ``integrations.normalisiere_kaeufe``.
    """
    rows: list[dict] = []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return rows
    for order in root.iter():
        if _local(order.tag) != "Order":
            continue
        created = _find(order, "CreatedTime")
        datum = (created.text[:10] if created is not None and created.text else None)
        # Pro Transaktion (Artikel) eine Zeile.
        for trans in order.iter():
            if _local(trans.tag) != "Transaction":
                continue
            item = _find(trans, "Item")
            item_id = _find(item, "ItemID") if item is not None else None
            sku = _find(item, "SKU") if item is not None else None
            preis = _find(trans, "TransactionPrice")
            pid = None
            if sku is not None and sku.text:
                pid = sku.text.strip()
            elif item_id is not None and item_id.text:
                pid = item_id.text.strip()
            if not pid:
                continue
            rows.append({
                "product_id": pid,
                "date": datum,
                "price": (preis.text.strip() if preis is not None and preis.text else "0"),
            })
    return rows


@dataclass
class EbayTradingClient:
    access_token: str
    environment: str = "production"
    site_id: str = _SITEID_DE
    _sender: Callable[..., str] = field(default=http_text, repr=False)

    def _headers(self, call_name: str) -> dict:
        return {
            "X-EBAY-API-CALL-NAME": call_name,
            "X-EBAY-API-SITEID": self.site_id,
            "X-EBAY-API-COMPATIBILITY-LEVEL": _COMPAT_LEVEL,
            "X-EBAY-API-IAF-TOKEN": self.access_token,   # OAuth-Access-Token
            "Content-Type": "text/xml",
        }

    def get_buyer_orders_xml(self, *, tage: int = 90, seite: int = 1) -> str:
        """Roh-XML der GetOrders-Antwort (OrderRole=Buyer) fuer die letzten ``tage``."""
        tage = min(max(tage, 1), 90)   # eBay-Grenze ~90 Tage
        ende = datetime.utcnow()
        start = ende - timedelta(days=tage)
        body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            f'<GetOrdersRequest xmlns="{_NS}">'
            '<OrderRole>Buyer</OrderRole>'
            '<OrderStatus>Completed</OrderStatus>'
            f'<CreateTimeFrom>{start.strftime("%Y-%m-%dT%H:%M:%S.000Z")}</CreateTimeFrom>'
            f'<CreateTimeTo>{ende.strftime("%Y-%m-%dT%H:%M:%S.000Z")}</CreateTimeTo>'
            f'<Pagination><EntriesPerPage>100</EntriesPerPage><PageNumber>{seite}</PageNumber></Pagination>'
            '</GetOrdersRequest>'
        ).encode("utf-8")
        return self._sender(_TRADING_URL[self.environment], method="POST",
                            body=body, headers=self._headers("GetOrders"))

    def get_buyer_purchases(self, *, tage: int = 90) -> list[dict]:
        """Holt die Kaeufe der letzten ``tage`` und gibt normalisierte Zeilen zurueck."""
        return parse_buyer_orders(self.get_buyer_orders_xml(tage=tage))
