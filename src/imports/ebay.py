"""eBay-Import (read-only).

Normalisiert Zeilen aus eBay-Finanz-/Transaktionsreports zu ``PlatformSale``.
Gebuehren, Versand, Refunds und von eBay abgefuehrte USt (Deemed-Supplier) werden
GETRENNT gefuehrt — eine eBay-Auszahlung ist nicht gleich ein Einzelumsatz
(Abschnitt 5.1/5.4 der Spezifikation).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Iterable

from ..models import PlatformSale, Source, TaxScheme


def _dec(value, default: str = "0") -> Decimal:
    if value in (None, ""):
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value).replace(",", "."))


def _datum(value) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def importiere_ebay_verkaeufe(rows: list[dict]) -> list[PlatformSale]:
    """Wandelt eBay-Reportzeilen in ``PlatformSale``-Objekte um.

    Erwartete (tolerante) Felder pro Zeile: ``id``, ``date``, ``gross``/``brutto``,
    ``fees``/``gebuehren``, ``shipping``/``versand``, ``refund``,
    ``collected_vat`` (von eBay abgefuehrt), ``product_id``, ``buyer_country``,
    ``tax_scheme`` (``regel``/``differenz``).
    """
    result: list[PlatformSale] = []
    for i, row in enumerate(rows):
        scheme_raw = str(row.get("tax_scheme", "regel")).lower()
        scheme = TaxScheme.DIFFERENZ if scheme_raw == "differenz" else TaxScheme.REGEL
        result.append(PlatformSale(
            id=str(row.get("id") or f"ebay-{i + 1}"),
            datum=_datum(row.get("date") or row.get("datum")),
            plattform=Source.EBAY,
            brutto=_dec(row.get("gross") or row.get("brutto")),
            gebuehren=_dec(row.get("fees") or row.get("gebuehren")),
            versand=_dec(row.get("shipping") or row.get("versand")),
            refund=_dec(row.get("refund")),
            product_id=row.get("product_id"),
            customer_country=str(row.get("buyer_country") or row.get("country") or "DE").upper(),
            tax_scheme=scheme,
            ebay_collected_vat=_dec(row.get("collected_vat") or row.get("ebay_collected_vat")),
        ))
    return result


def netto_auszahlung(sale: PlatformSale) -> Decimal:
    """Erwartete Netto-Auszahlung eines Verkaufs (Brutto - Gebuehren - Refund).

    Versand ist hier nicht abgezogen, da er je nach Konstellation eingenommen ODER
    ausgegeben wird; die Reconciliation gleicht gegen den tatsaechlichen Bankbetrag ab.
    """
    return sale.brutto - sale.gebuehren - sale.refund
