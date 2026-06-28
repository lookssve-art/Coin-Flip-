"""eBay-Kaeufe -> Einkaufspreise (fuer § 25a-Differenzbesteuerung).

Zieht die Einkaufspreise aus der eBay-Kaufhistorie ("Mein eBay > Kaufe"). Die
oeffentliche eBay-API stellt die persoenliche Kaufhistorie nicht frei bereit, daher
ist die verlaessliche Quelle der **Bestellverlauf-Export** (JSON/CSV) bzw. Zeilen,
die eine vorgelagerte Stufe liefert. Dieser Adapter normalisiert die Kaufzeilen zu
einer ``{product_id: einkaufspreis}``-Map — gefiltert ab dem Geschaeftsbeginn.

Mehrere Kaeufe desselben Artikels: der **letzte** Kauf ab Geschaeftsbeginn gewinnt
(zeitlich passend zum spaeteren Verkauf). Kaeufe vor dem Geschaeftsbeginn (private
Anschaffung) werden ausgeschlossen.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from ..util.datum import parse_iso, ab_geschaeftsbeginn


def _preis(value) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", "."))
    except InvalidOperation:
        return None


def normalisiere_kaeufe(
    rows: list[dict], *, ab: Optional[date] = None
) -> tuple[dict[str, Decimal], list[dict]]:
    """Wandelt Kaufzeilen in ``{product_id: preis}`` (ab Geschaeftsbeginn).

    Erwartete (tolerante) Felder je Zeile: ``product_id``/``item_id``/``sku``,
    ``date``/``purchase_date``, ``price``/``total``/``preis``.
    Rueckgabe: (einkaufspreise, ignoriert_vor_beginn).
    """
    einkaufspreise: dict[str, Decimal] = {}
    letztes_datum: dict[str, date] = {}
    ignoriert: list[dict] = []

    for r in rows:
        pid = r.get("product_id") or r.get("item_id") or r.get("sku")
        preis = _preis(r.get("price") or r.get("total") or r.get("preis"))
        d = parse_iso(r.get("date") or r.get("purchase_date"))
        if not pid or preis is None:
            continue
        if not ab_geschaeftsbeginn(d, ab):
            ignoriert.append(r)        # private Anschaffung vor Gruendung
            continue
        # Letzter Kauf ab Beginn gewinnt (None-Datum verliert gegen datierte).
        bisher = letztes_datum.get(pid)
        if pid not in einkaufspreise or (d and (bisher is None or d >= bisher)):
            einkaufspreise[pid] = preis
            if d:
                letztes_datum[pid] = d

    return einkaufspreise, ignoriert
