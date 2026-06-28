"""Heuristische Feldextraktion aus OCR-Rohtext (deutsche Belege).

Zieht Datum, Brutto-/Nettobetrag, USt-Satz und -Betrag sowie den Haendler aus dem
erkannten Text. Bewusst regelbasiert und konservativ: jeder unsichere Wert senkt
die Confidence, sodass die Pipeline den Beleg in die Review-Queue gibt, statt zu
raten (keine Halluzination — Abschnitt 4 der Spezifikation).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

# Betrag im deutschen Format: 1.234,56 oder 1234,56 oder 12,00
_BETRAG = r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})"
_SUMME_RE = re.compile(
    r"(?:summe|gesamt(?:betrag)?|total|zu\s*zahlen|betrag)\D{0,15}" + _BETRAG, re.IGNORECASE)
_UST_SATZ_RE = re.compile(r"(\d{1,2})\s*%\s*(?:mwst|ust|umsatzsteuer)?", re.IGNORECASE)
_UST_BETRAG_RE = re.compile(
    r"(?:mwst|ust|umsatzsteuer)\D{0,15}" + _BETRAG, re.IGNORECASE)
_DATUM_RE = re.compile(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})")


def _to_decimal(s: str) -> Optional[Decimal]:
    try:
        return Decimal(s.replace(".", "").replace(",", "."))
    except (InvalidOperation, AttributeError):
        return None


@dataclass
class ExtraktionsErgebnis:
    datum: Optional[date] = None
    haendler: Optional[str] = None
    brutto: Optional[Decimal] = None
    netto: Optional[Decimal] = None
    ust_satz: Optional[Decimal] = None
    ust_betrag: Optional[Decimal] = None
    confidence: float = 0.0
    fehlend: list[str] = field(default_factory=list)


def _parse_datum(text: str) -> Optional[date]:
    m = _DATUM_RE.search(text)
    if not m:
        return None
    tag, monat, jahr = m.groups()
    jahr_i = int(jahr)
    if jahr_i < 100:
        jahr_i += 2000
    try:
        return date(jahr_i, int(monat), int(tag))
    except ValueError:
        return None


def _haendler(text: str) -> Optional[str]:
    # Heuristik: erste nicht-leere Zeile mit Buchstaben ist meist der Haendlername.
    for zeile in text.splitlines():
        z = zeile.strip()
        if len(z) >= 3 and re.search(r"[A-Za-zÄÖÜäöü]", z):
            return z[:80]
    return None


def extrahiere_felder(text: str) -> ExtraktionsErgebnis:
    """Extrahiert strukturierte Felder aus OCR-Text. Confidence in [0, 1]."""
    res = ExtraktionsErgebnis()
    text = text or ""

    res.datum = _parse_datum(text)
    res.haendler = _haendler(text)

    summe = _SUMME_RE.search(text)
    if summe:
        res.brutto = _to_decimal(summe.group(1))

    satz = _UST_SATZ_RE.search(text)
    if satz:
        kandidat = Decimal(satz.group(1))
        if kandidat in (Decimal("7"), Decimal("19")):
            res.ust_satz = kandidat

    ust = _UST_BETRAG_RE.search(text)
    if ust:
        res.ust_betrag = _to_decimal(ust.group(1))

    # Netto aus Brutto/Satz ableiten, falls moeglich.
    if res.brutto is not None and res.ust_satz is not None:
        faktor = Decimal("1") + res.ust_satz / Decimal("100")
        res.netto = (res.brutto / faktor).quantize(Decimal("0.01"))
        if res.ust_betrag is None:
            res.ust_betrag = (res.brutto - res.netto).quantize(Decimal("0.01"))

    # Confidence aus Vollstaendigkeit der Pflichtfelder.
    pflicht = {"datum": res.datum, "brutto": res.brutto, "ust_satz": res.ust_satz}
    vorhanden = sum(1 for v in pflicht.values() if v is not None)
    res.fehlend = [k for k, v in pflicht.items() if v is None]
    res.confidence = round(vorhanden / len(pflicht), 2)
    return res
