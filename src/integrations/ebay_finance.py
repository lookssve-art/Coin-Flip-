"""eBay Finances API (read-only) — Transaktionen + Gebuehren abrufen.

Liest Verkaeufe, Gebuehren und Refunds aus ``/sell/finances/v1/transaction`` und
bringt sie in das Zeilenformat von ``src.imports.ebay.importiere_ebay_verkaeufe``.
Strikt lesend. Der HTTP-Getter ist injizierbar (offline testbar).

WICHTIG: Die Finances-API verlangt digitale Signaturen (RFC 9421). Wird ein
``signing``-Schluessel uebergeben, signiert der Client jeden Call (Header
``x-ebay-signature-key``/``Signature``/``Signature-Input``). Ohne Signatur
antwortet eBay mit HTTP 403 / errorId 215001.

Mapping (konservativ, dokumentiert):
  * SALE   -> gross = amount, fees = totalFeeAmount
  * REFUND -> refund = amount (eigener Vorgang)
  * sonstige (NON_SALE_CHARGE, DISPUTE, ...) -> als Gebuehr gefuehrt, markiert.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Callable, Optional
from urllib.parse import urlencode, urlsplit

from ..util.http import http_json
from . import ebay_signature

_FINANCES_BASE = {
    "production": "https://apiz.ebay.com/sell/finances/v1",
    "sandbox": "https://apiz.sandbox.ebay.com/sell/finances/v1",
}


@dataclass
class SigningContext:
    """Material zum Signieren von Finances-Requests."""
    jwe: str
    seed: bytes
    clock: Callable[[], int] = field(default=lambda: 0, repr=False)


@dataclass
class EbayFinanceClient:
    access_token: str
    marketplace_id: str = "EBAY_DE"
    environment: str = "production"
    signing: Optional[SigningContext] = None
    _getter: Callable[..., dict] = field(default=http_json, repr=False)

    def _headers(self, *, path: str, authority: str, method: str = "GET",
                 body: bytes = b"") -> dict:
        hdrs = {
            "Authorization": f"Bearer {self.access_token}",
            "X-EBAY-C-MARKETPLACE-ID": self.marketplace_id,
            "Accept": "application/json",
        }
        if self.signing:
            hdrs.update(ebay_signature.build_signature_headers(
                method=method, path=path, authority=authority,
                jwe=self.signing.jwe, seed=self.signing.seed,
                created=self.signing.clock(), body=body,
            ))
        return hdrs

    def get_transactions(self, *, start: date, end: date, limit: int = 200,
                         offset: int = 0) -> list[dict]:
        """Holt rohe Transaktionen im Zeitraum [start, end] (eine Seite)."""
        flt = (f"transactionDate:[{start.isoformat()}T00:00:00.000Z.."
               f"{end.isoformat()}T23:59:59.999Z]")
        base = _FINANCES_BASE[self.environment]
        query = urlencode({"filter": flt, "limit": limit, "offset": offset})
        url = f"{base}/transaction?{query}"
        sp = urlsplit(url)
        headers = self._headers(path=f"{sp.path}?{sp.query}", authority=sp.netloc)
        data = self._getter(url, headers=headers)
        return data.get("transactions", [])

    def get_all_transactions(self, *, start: date, end: date,
                             seiten_limit: int = 50) -> list[dict]:
        """Holt ALLE Transaktionen (paginiert ueber offset, bis leer)."""
        alle: list[dict] = []
        offset = 0
        for _ in range(seiten_limit):
            seite = self.get_transactions(start=start, end=end, limit=200, offset=offset)
            if not seite:
                break
            alle.extend(seite)
            if len(seite) < 200:
                break
            offset += 200
        return alle

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
                row.update({"fees": betrag, "_review": f"unklarer Typ: {typ}"})
            rows.append(row)
        return rows

    @staticmethod
    def fee_summary(transactions: list[dict]) -> dict:
        """Aggregiert die echten eBay-Gebuehren aus den Transaktionen.

        Gebuehren = Summe ``totalFeeAmount`` der SALE-Transaktionen
        + Betraege separater Gebuehrenbuchungen (NON_SALE_CHARGE, SHIPPING_LABEL).
        Liefert Decimals und die Anzahl Verkaeufe.
        """
        fees = Decimal("0")
        sales_gross = Decimal("0")
        refunds = Decimal("0")
        n_sales = 0
        for t in transactions:
            typ = (t.get("transactionType") or "").upper()
            if typ == "SALE":
                n_sales += 1
                fees += _dec(t.get("totalFeeAmount"))
                sales_gross += _dec(t.get("amount")) + _dec(t.get("totalFeeAmount"))
            elif typ in ("NON_SALE_CHARGE", "SHIPPING_LABEL"):
                fees += abs(_dec(t.get("amount")))
            elif typ in ("REFUND", "CREDIT"):
                refunds += _dec(t.get("amount"))
        return {
            "fees_total": fees.quantize(Decimal("0.01")),
            "sales_gross": sales_gross.quantize(Decimal("0.01")),
            "refunds_total": refunds.quantize(Decimal("0.01")),
            "n_sales": n_sales,
        }


def _amount(node) -> str:
    if isinstance(node, dict):
        return str(node.get("value", "0"))
    return "0"


def _dec(node) -> Decimal:
    try:
        return Decimal(_amount(node))
    except Exception:
        return Decimal("0")


def _land(t: dict) -> str:
    buyer = t.get("buyer") or {}
    return (buyer.get("country") or "DE").upper()
