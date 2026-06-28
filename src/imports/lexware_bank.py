"""Bankimport aus Lexware Office (Geschaeftskonto-CSV-Export).

Lexware Office dient hier zugleich als Geschaeftskonto. Die oeffentliche Lexware-API
gibt Kontoumsaetze nicht zuverlaessig als Roh-Transaktionen heraus — der robuste,
nachvollziehbare Weg ist der CSV-Export der Kontoumsaetze. Dieser Adapter liest den
Export tolerant (deutsche Spaltennamen/Beträge) und erzeugt Bank-``Transaction``s
ueber den bestehenden, idempotenten Importer.
"""

from __future__ import annotations

import csv
import io
import os
from typing import Optional

from ..models import Transaction
from .bank import importiere_bank_transaktionen

# Tolerante Header-Erkennung: lowercase-Teilstring -> internes Feld.
_DATE_HINTS = ("buchungstag", "buchungsdatum", "datum", "valuta", "wertstellung", "date")
_AMOUNT_HINTS = ("betrag", "umsatz", "amount")
_TEXT_HINTS = ("verwendungszweck", "buchungstext", "beschreibung", "name",
               "auftraggeber", "empfaenger", "empfänger", "beguenstigter",
               "zahlungspflichtiger", "reference", "description")


def _match_spalte(header: list[str], hints) -> Optional[str]:
    for spalte in header:
        low = spalte.strip().lower()
        if any(h in low for h in hints):
            return spalte
    return None


def _read_text(path: str) -> str:
    with open(path, "rb") as fh:
        raw = fh.read()
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def lese_lexware_bank_csv(path: str, *, mapping: Optional[dict] = None) -> list[dict]:
    """Liest den CSV-Export und liefert normalisierte Zeilen fuer den Bank-Importer.

    ``mapping`` kann die Spaltennamen explizit setzen
    (``{"date": "...", "amount": "...", "text": "..."}``); ohne Mapping wird der
    Header tolerant erkannt.
    """
    text = _read_text(path)
    # Trennzeichen automatisch erkennen (; oder ,).
    sample = text[:2048]
    delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    header = reader.fieldnames or []

    mapping = mapping or {}
    date_col = mapping.get("date") or _match_spalte(header, _DATE_HINTS)
    amount_col = mapping.get("amount") or _match_spalte(header, _AMOUNT_HINTS)
    text_cols = ([mapping["text"]] if mapping.get("text")
                 else [c for c in header if any(h in c.strip().lower() for h in _TEXT_HINTS)])
    if not date_col or not amount_col:
        raise ValueError(
            f"Bank-CSV: Datums-/Betragsspalte nicht erkannt (Header: {header}). "
            "Mapping in config.integrationen.bank.csv_mapping setzen.")

    rows: list[dict] = []
    for r in reader:
        if not (r.get(date_col) or "").strip():
            continue
        beschreibung = " ".join(
            (r.get(c) or "").strip() for c in text_cols if (r.get(c) or "").strip())
        rows.append({"date": r[date_col].strip(),
                     "amount": (r.get(amount_col) or "").strip(),
                     "description": beschreibung})
    return rows


def importiere_lexware_bank(path: str, *, mapping: Optional[dict] = None) -> list[Transaction]:
    """CSV-Export -> deduplizierte Bank-``Transaction``s (Ist-Prinzip)."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    return importiere_bank_transaktionen(lese_lexware_bank_csv(path, mapping=mapping))
