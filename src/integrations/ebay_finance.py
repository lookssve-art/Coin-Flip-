"""eBay Finances API (read-only) — Transaktionen abrufen und normalisieren.

Liest Verkaeufe, Gebuehren und Refunds aus ``/sell/finances/v1/transaction`` und
bringt sie in das Zeilenformat von ``src.imports.ebay.importiere_ebay_verkaeufe``.
Strikt lesend (keine schreibenden Endpunkte). Der HTTP-Getter ist injizierbar.

Mapping (konservativ, dokumentiert):
  * SALE   -> gross = amount, fees = totalFeeAmount
  * REFUND -> refund = amount (als eigener Vorgang)
  * sonstige (NON_SALE_CHARGE, DISPUTE, ...) -> als Gebuehr gefuehrt, markiert.
Unklare Faelle werden nicht geraten, sondern mit ``_review`` markiert.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from ..util.http import http_json

_FINANCES_BASE = {
    "production": "https://apiz.ebay.com/sell/finances/v1",
    "sandbox": "https://apiz.sandbox.ebay.com/sell/finances/v1",
}


@dataclass
class EbayFinanceClient:
    access_token: str
    marketplace_id: str = "EBAY_DE"
    environment: str = "production"
    _getter: Callable[..., dict] = field(default=http_json, repr=False)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "X-EBAY-C-MARKETPLACE-ID": self.marketplace_id,
            "Accept": "application/json",
        }

    def get_transactions(self, *, start: date, end: date, limit: int = 200,
                         offset: int = 0) -> list[dict]:
        """Holt rohe Transaktionen im Zeitraum [start, end] (eine Seite)."""
        # eBay erwartet ISO-8601 Zeitstempel im transactionDate-Filter.
        flt = (f"transactionDate:[{start.isoformat()}T00:00:00.000Z.."
               f"{end.isoformat()}T23:59:59.999Z]")
        base = _FINANCES_BASE[self.environment]
        from urllib.parse import urlencode
        query = urlencode({"filter": flt, "limit": limit, "offset": offset})
        data = self._getter(f"{base}/transaction?{query}", headers=self._headers())
        return data.get("transactions", [])

    @staticmethod
    def to_rows(transactions: list[dict]) -> list[dict]:
        """Normalisiert rohe Finances-Transaktionen in importierbare Zeilen."""
        rows: list[dict] = []
        for t in transactions:
            typ = (t.get("transactionType") or "").upper()
            betrag = _amount(t.get("amount"))
            row = {
                "id": t.get("transactionId") or t.get("orderId") or "",
                "date": (t.get("transactionDate") or "")[:10],
                "buyer_country": _land(t),
            }
            if typ == "SALE":
                row.update({"gross": betrag, "fees": _amount(t.get("totalFeeAmount"))})
            elif typ in ("REFUND", "CREDIT"):
                row.update({"refund": betrag})
            else:
                # Nicht eindeutig zuordenbar -> als Gebuehr fuehren und markieren.
                row.update({"fees": betrag, "_review": f"unklarer Typ: {typ}"})
            rows.append(row)
        return rows


def _amount(node) -> str:
    if isinstance(node, dict):
        return str(node.get("value", "0"))
    return "0"


def _land(t: dict) -> str:
    buyer = t.get("buyer") or {}
    return (buyer.get("country") or "DE").upper()
