"""Datums-Hilfen: Geschaeftsbeginn-Cutoff und EU-Laenderliste.

Der Geschaeftsbeginn ist der harte Stichtag: alle Belege, Banktransaktionen und
Verkaeufe VOR diesem Datum gehoeren in die private Sphaere und werden ignoriert
(Abschnitt 4 — keine Vermischung; saubere Trennung ab Gruendung).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

# EU-Mitgliedstaaten (ISO-2) — fuer OSS-Fernverkauf-Schwelle relevant.
EU_LAENDER = frozenset({
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
    "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
    "SI", "ES", "SE",
})


def parse_iso(value) -> Optional[date]:
    """Wandelt einen ISO-Datums-/Timestamp-String oder date in ein date."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value).strip()
    if "T" in s:
        s = s.split("T", 1)[0]
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def ab_geschaeftsbeginn(d: Optional[date], beginn: Optional[date]) -> bool:
    """True, wenn ``d`` am/nach dem Geschaeftsbeginn liegt (oder kein Beginn gesetzt)."""
    if beginn is None:
        return True
    if d is None:
        return False   # ohne Datum nicht eindeutig zuzuordnen -> ausschliessen
    return d >= beginn


def ist_eu_b2c_fernverkauf(land: str, *, inland: str = "DE") -> bool:
    """True bei B2C-Lieferung in ein anderes EU-Land (OSS-relevant)."""
    land = (land or "").upper()
    return land in EU_LAENDER and land != inland.upper()
