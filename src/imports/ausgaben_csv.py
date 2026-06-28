"""Manuelle Ausgaben/Rechnungen aus einer einfachen CSV.

Fuer echte Belege (Versand, Material, Buero, Gebuehren), die nicht automatisch
abgerufen werden koennen. Format (Semikolon oder Komma):

    datum;kategorie;betrag;beschreibung
    2026-06-10;versand;4,90;DHL Paket
    2026-06-12;buero;19,99;Druckerpapier

Die Zeilen werden als ``Receipt`` gefuehrt und fliessen in EÜR/Reconciliation.
"""

from __future__ import annotations

import csv
import io
import os
from datetime import date
from decimal import Decimal, InvalidOperation

from ..models import Receipt
from ..util.datum import parse_iso


def lese_ausgaben_csv(path: str) -> list[Receipt]:
    """Liest die Ausgaben-CSV und gibt ``Receipt``-Objekte zurueck."""
    if not path or not os.path.exists(path):
        return []
    with open(path, "rb") as fh:
        raw = fh.read()
    text = None
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        return []
    delimiter = ";" if text[:2048].count(";") >= text[:2048].count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    receipts: list[Receipt] = []
    for i, row in enumerate(reader, start=1):
        low = {(k or "").strip().lower(): _zelle(v) for k, v in row.items()}
        betrag = _to_decimal(low.get("betrag") or low.get("summe") or low.get("brutto"))
        if betrag is None or betrag <= 0:
            continue
        datum = parse_iso(low.get("datum") or low.get("date")) or date.today()
        kategorie = (low.get("kategorie") or low.get("category") or "sonstiges").lower()
        beschreibung = low.get("beschreibung") or low.get("text") or ""
        receipts.append(Receipt(
            id=f"AUSGABE-{i:04d}", datum=datum, haendler=beschreibung or kategorie,
            brutto=betrag, netto=betrag, ust_satz=Decimal("0"), ust_betrag=Decimal("0"),
            kategorie=kategorie, vorsteuer_abzug="nein",
        ))
    return receipts


def _zelle(v) -> str:
    """Normalisiert einen Zellwert; ueberzaehlige Spalten (DictReader) werden Liste."""
    if isinstance(v, list):
        v = v[0] if v else ""
    return (v or "").strip()


def _to_decimal(s) -> Decimal | None:
    if not s:
        return None
    s = str(s).strip().replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None
