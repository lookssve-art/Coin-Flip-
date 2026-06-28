"""Bank-Import (read-only).

Normalisiert Rohzeilen eines Geschaeftskontos (Qonto/Finom-REST oder PSD2-Aggregator)
zu ``Transaction``-Objekten. Direkter Bankzugriff ist meist nur lesend (SCA/Re-Auth
alle 90 Tage) — daher strikt read-only.

Idempotenz: jede Transaktion erhaelt einen stabilen Key aus (Datum, Betrag,
normalisierter Beschreibung). Erneuter Import derselben Zeile erzeugt denselben Key
-> keine Doppelbuchung (Abschnitt 8 der Spezifikation).
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable

from ..models import Transaction, Source

# Haeufige Feldnamen verschiedener Anbieter -> internes Schema.
_DATUM_KEYS = ("date", "datum", "booking_date", "settled_at", "valueDate", "value_date")
_BETRAG_KEYS = ("amount", "betrag", "value")
_TEXT_KEYS = ("reference", "description", "label", "beschreibung", "counterparty_name", "note")


def _first(row: dict, keys: Iterable[str]):
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return None


def _parse_datum(value) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value).strip()
    # ISO-Timestamp (2026-06-01T12:30:00[...]) -> auf das Datum reduzieren.
    if "T" in s:
        s = s.split("T", 1)[0]
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # Letzter Versuch: nur die ersten 10 Zeichen als ISO-Datum.
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def _parse_betrag(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    s = str(value).strip().replace(" ", "").replace(" ", "")
    # Deutsche Schreibweise 1.234,56 -> 1234.56
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"Betrag nicht parsebar: {value!r}") from exc


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def idempotency_key(datum: date, betrag: Decimal, beschreibung: str) -> str:
    material = f"{datum.isoformat()}|{betrag}|{_normalize_text(beschreibung)}"
    return "bank-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def importiere_bank_transaktionen(
    rows: list[dict], *, source: Source = Source.BANK
) -> list[Transaction]:
    """Wandelt Rohzeilen in ``Transaction`` um und dedupliziert ueber den Idempotenz-Key."""
    seen: set[str] = set()
    result: list[Transaction] = []
    for i, row in enumerate(rows):
        datum = _parse_datum(_first(row, _DATUM_KEYS))
        betrag = _parse_betrag(_first(row, _BETRAG_KEYS))
        beschreibung = str(_first(row, _TEXT_KEYS) or "")
        key = row.get("id") and f"bank-{row['id']}" or idempotency_key(datum, betrag, beschreibung)
        if key in seen:
            continue
        seen.add(key)
        result.append(Transaction(
            id=key,
            datum=datum,
            betrag=betrag,
            source=source,
            beschreibung=beschreibung,
            idempotency_key=key,
        ))
    return result
