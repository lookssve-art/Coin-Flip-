"""Billbee-API (read-only) — Bestellungen abrufen und normalisieren.

Billbee verwaltet die Multichannel-Bestellungen/Rechnungen; der SERO-Agent liest
sie und legt die deutsche Steuer-Logik (§25a, §13b, §19-Schwellen, EÜR/BWA) darüber.

Auth (laut Billbee): HTTP-Basic (Billbee-Login : API-Passwort aus den Kontoeinstellungen)
PLUS Header ``X-Billbee-Api-Key`` (Partner-/App-Key). API-Zugang muss bei Billbee
freigeschaltet sein; Rate-Limit ~2 Requests/s.

Der Parser ist bewusst tolerant (mehrere mögliche Feldnamen), weil die genaue
Billbee-Antwort je Konto/Version variiert — Feldnamen bei Bedarf gegen die echten
Daten prüfen (`billbee-sync` schreibt das Rohformat mit).
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable
from urllib.parse import urlencode

from ..util.http import http_json

_BASE = "https://api.billbee.io/api/v1"


def _q(x) -> str:
    try:
        return str(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except Exception:  # noqa: BLE001
        return "0.00"


def _first(d: dict, *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return default


def parse_billbee_orders(raw: dict, *, default_tax_scheme: str = "differenz") -> list[dict]:
    """Normalisiert eine Billbee-/orders-Antwort in Zeilen fuer importiere_ebay_verkaeufe.

    Eine Zeile pro BESTELLUNG (wie Billbees 1 Rechnung/Bestellung). Positionstitel
    werden zusammengefasst; gross = Bestell-Gesamtbetrag.
    """
    daten = raw.get("Data") if isinstance(raw, dict) else raw
    if not isinstance(daten, list):
        return []
    rows: list[dict] = []
    for o in daten:
        if not isinstance(o, dict):
            continue
        oid = str(_first(o, "OrderNumber", "BillBeeOrderId", "Id", default=""))
        datum = str(_first(o, "CreatedAt", "OrderDate", "ConfirmedAt", default=""))[:10]
        items = o.get("OrderItems") or o.get("Items") or []
        titel_liste, menge_gesamt, summe_items = [], 0, Decimal("0")
        for it in items:
            prod = it.get("Product") or {}
            t = _first(prod, "Title", "Name") or _first(it, "Title", "Name") or ""
            if t:
                titel_liste.append(str(t))
            try:
                menge_gesamt += int(float(_first(it, "Quantity", "Amount", default=1)))
            except Exception:  # noqa: BLE001
                menge_gesamt += 1
            summe_items += _dec(_first(it, "TotalPrice", "TotalGross", "Price", default=0))
        gross = _first(o, "TotalCost", "TotalGross", "PaidAmount")
        gross = _dec(gross) if gross is not None else summe_items
        titel = "; ".join(titel_liste[:5]) or "Bestellung"
        if len(titel_liste) > 5:
            titel += " u. a."
        addr = o.get("ShippingAddress") or o.get("Customer") or {}
        name = (_first(addr, "Name")
                or " ".join(x for x in (_first(addr, "FirstName", default=""),
                                        _first(addr, "LastName", default="")) if x).strip())
        land = str(_first(addr, "CountryCode", "Country", default="DE"))[:2].upper() or "DE"
        rows.append({
            "id": oid,
            "date": datum,
            "gross": _q(gross),
            "quantity": str(max(menge_gesamt, 1)),
            "product_id": str(_first((items[0].get("Product") if items else {}) or {},
                                     "SKU", default="") or ""),
            "title": titel,
            "buyer_country": land,
            "buyer_name": name or "",
            "buyer_street": str(_first(addr, "Street", "Address1", default="")),
            "buyer_zip": str(_first(addr, "Zip", "PostalCode", default="")),
            "buyer_city": str(_first(addr, "City", default="")),
            "tax_scheme": default_tax_scheme,
            "quelle": "billbee",
        })
    return rows


def _dec(v) -> Decimal:
    try:
        return Decimal(str(v).replace(",", "."))
    except Exception:  # noqa: BLE001
        return Decimal("0")


@dataclass
class BillbeeClient:
    api_key: str                      # X-Billbee-Api-Key (Partner-/App-Key)
    user: str                         # Billbee-Login
    api_password: str                 # API-Passwort aus den Billbee-Kontoeinstellungen
    base_url: str = _BASE
    _getter: Callable[..., dict] = field(default=http_json, repr=False)

    def _headers(self) -> dict:
        basic = base64.b64encode(f"{self.user}:{self.api_password}".encode()).decode()
        return {"X-Billbee-Api-Key": self.api_key,
                "Authorization": "Basic " + basic,
                "Accept": "application/json"}

    def get_orders(self, *, von: str, bis: str = "", page: int = 1,
                   page_size: int = 250) -> dict:
        """Holt eine Seite Bestellungen im Zeitraum [von, bis] (ISO-Datum)."""
        params = {"minOrderDate": von, "page": page, "pageSize": page_size}
        if bis:
            params["maxOrderDate"] = bis
        url = f"{self.base_url.rstrip('/')}/orders?{urlencode(params)}"
        return self._getter(url, headers=self._headers())

    def alle_bestellungen(self, *, von: str, bis: str = "",
                          default_tax_scheme: str = "differenz",
                          seiten_limit: int = 40) -> list[dict]:
        """Holt ALLE Bestellungen (paginiert) und normalisiert sie zu Zeilen."""
        alle: list[dict] = []
        for page in range(1, seiten_limit + 1):
            raw = self.get_orders(von=von, bis=bis, page=page)
            rows = parse_billbee_orders(raw, default_tax_scheme=default_tax_scheme)
            if not rows:
                break
            alle.extend(rows)
            paging = (raw.get("Paging") or {}) if isinstance(raw, dict) else {}
            if page >= int(paging.get("TotalPages", page) or page):
                break
        return alle
