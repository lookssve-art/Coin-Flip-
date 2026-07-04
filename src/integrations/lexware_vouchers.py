"""Lexware Office — hinterlegte Belege (Vouchers) LESEN.

Damit sieht der Agent, was in Lexware bereits gebucht ist: die vom Nutzer als
Foto hinterlegten Einkaufsbelege (Wareneinkauf), Ausgaben usw. Über
``GET /v1/voucherlist`` (Liste, gefiltert nach Typ/Status/Datum) — read-only.

Feldnamen defensiv (Lexware liefert je nach Version leicht anders); beim ersten
echten Abruf gegen die Doku prüfen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable
from urllib.parse import urlencode

from ..util.http import http_json


def _dec(v) -> Decimal:
    try:
        return Decimal(str(v).replace(",", "."))
    except Exception:  # noqa: BLE001
        return Decimal("0")


def parse_voucherlist(raw: dict) -> list[dict]:
    """Normalisiert eine /voucherlist-Antwort in einfache Beleg-Dicts."""
    inhalt = raw.get("content") if isinstance(raw, dict) else raw
    if not isinstance(inhalt, list):
        return []
    belege = []
    for v in inhalt:
        if not isinstance(v, dict):
            continue
        betrag = v.get("totalAmount", v.get("totalGrossAmount", v.get("openAmount", 0)))
        belege.append({
            "id": str(v.get("id", "")),
            "typ": v.get("voucherType", ""),
            "status": v.get("voucherStatus", ""),
            "nummer": str(v.get("voucherNumber", "") or ""),
            "datum": str(v.get("voucherDate", ""))[:10],
            "kontakt": v.get("contactName", "") or "",
            "betrag": str(_dec(betrag).quantize(Decimal("0.01"))),
            "waehrung": v.get("currency", "EUR"),
            "archiviert": bool(v.get("archived", False)),
        })
    return belege


@dataclass
class LexwareVoucherReader:
    api_key: str
    base_url: str = "https://api.lexware.io/v1"
    _getter: Callable[..., dict] = field(default=http_json, repr=False)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}

    def voucherliste(self, *, typ: str = "purchaseinvoice", status: str = "open,paid,unchecked",
                     von: str = "", page: int = 0, size: int = 100) -> dict:
        """Eine Seite Belege (voucherType/voucherStatus sind bei Lexware Pflichtfilter)."""
        params = {"voucherType": typ, "voucherStatus": status, "page": page, "size": size}
        if von:
            params["voucherDateFrom"] = von
        url = f"{self.base_url.rstrip('/')}/voucherlist?{urlencode(params)}"
        return self._getter(url, headers=self._headers())

    def alle_belege(self, *, typ: str = "purchaseinvoice,voucher",
                    status: str = "open,paid,unchecked", von: str = "",
                    seiten_limit: int = 50) -> list[dict]:
        """Holt ALLE Belege (paginiert) und normalisiert sie."""
        alle: list[dict] = []
        for page in range(0, seiten_limit):
            raw = self.voucherliste(typ=typ, status=status, von=von, page=page)
            belege = parse_voucherlist(raw)
            if not belege:
                break
            alle.extend(belege)
            total_pages = (int(raw.get("totalPages", page + 1) or (page + 1))
                           if isinstance(raw, dict) else page + 1)
            if page + 1 >= total_pages:
                break
        return alle
