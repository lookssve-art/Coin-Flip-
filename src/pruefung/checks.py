"""Formale Plausibilitaets-Checks (stdlib-only)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum


class Schwere(str, Enum):
    OK = "ok"
    HINWEIS = "hinweis"
    FEHLER = "fehler"


@dataclass
class Befund:
    feld: str
    schwere: Schwere
    nachricht: str

    @property
    def ok(self) -> bool:
        return self.schwere == Schwere.OK


# IBAN-Laenge je Land (Auszug der wichtigsten; weitere -> nur mod-97-Pruefung).
_IBAN_LAENGE = {
    "DE": 22, "AT": 20, "CH": 21, "FR": 27, "IT": 27, "ES": 24, "NL": 18,
    "BE": 16, "LU": 20, "PL": 28, "GB": 22, "DK": 18, "SE": 24, "FI": 18,
}


def pruefe_iban(iban: str) -> Befund:
    """ISO 7064 mod-97-Pruefung (und Laengencheck, soweit Land bekannt)."""
    if not iban:
        return Befund("iban", Schwere.HINWEIS, "Keine IBAN angegeben.")
    raw = re.sub(r"\s+", "", iban).upper()
    if not re.fullmatch(r"[A-Z]{2}[0-9]{2}[A-Z0-9]+", raw):
        return Befund("iban", Schwere.FEHLER, "IBAN-Format ungueltig.")
    land = raw[:2]
    erwartet = _IBAN_LAENGE.get(land)
    if erwartet and len(raw) != erwartet:
        return Befund("iban", Schwere.FEHLER,
                      f"IBAN-Laenge fuer {land} falsch ({len(raw)}, erwartet {erwartet}).")
    # mod-97: ersten 4 Zeichen ans Ende, Buchstaben -> Zahlen (A=10..Z=35).
    umgestellt = raw[4:] + raw[:4]
    ziffern = "".join(str(int(c, 36)) for c in umgestellt)
    if int(ziffern) % 97 != 1:
        return Befund("iban", Schwere.FEHLER, "IBAN-Pruefsumme falsch.")
    return Befund("iban", Schwere.OK, "IBAN gueltig.")


# USt-IdNr-Muster je Land (Format, nicht VIES-Online-Pruefung).
_UST_ID_MUSTER = {
    "DE": r"DE[0-9]{9}", "AT": r"ATU[0-9]{8}", "FR": r"FR[A-Z0-9]{2}[0-9]{9}",
    "IT": r"IT[0-9]{11}", "ES": r"ES[A-Z0-9][0-9]{7}[A-Z0-9]", "NL": r"NL[0-9]{9}B[0-9]{2}",
    "BE": r"BE[0-1][0-9]{9}", "LU": r"LU[0-9]{8}", "PL": r"PL[0-9]{10}",
    "DK": r"DK[0-9]{8}", "SE": r"SE[0-9]{12}", "FI": r"FI[0-9]{8}",
}


def pruefe_ust_id(ust_id: str) -> Befund:
    """Formatpruefung der USt-IdNr (keine VIES-Abfrage)."""
    if not ust_id:
        return Befund("ust_id", Schwere.HINWEIS, "Keine USt-IdNr angegeben.")
    raw = re.sub(r"\s+", "", ust_id).upper()
    land = raw[:2]
    muster = _UST_ID_MUSTER.get(land)
    if not muster:
        return Befund("ust_id", Schwere.HINWEIS, f"Land {land} ohne Formatregel — nicht geprueft.")
    if not re.fullmatch(muster, raw):
        return Befund("ust_id", Schwere.FEHLER, f"USt-IdNr-Format fuer {land} ungueltig.")
    return Befund("ust_id", Schwere.OK, "USt-IdNr-Format gueltig.")


def _dec(v) -> Decimal | None:
    try:
        return Decimal(str(v).replace(",", "."))
    except (InvalidOperation, AttributeError, ValueError):
        return None


def pruefe_rechnung_arithmetik(netto, ust_betrag, brutto, *,
                               toleranz=Decimal("0.02")) -> Befund:
    """Prueft netto + USt = brutto (Cent-Toleranz)."""
    n, u, b = _dec(netto), _dec(ust_betrag), _dec(brutto)
    if n is None or u is None or b is None:
        return Befund("arithmetik", Schwere.FEHLER, "Betrag nicht interpretierbar.")
    diff = (n + u - b).copy_abs()
    if diff > toleranz:
        return Befund("arithmetik", Schwere.FEHLER,
                      f"netto+USt ({n}+{u}={n+u}) != brutto ({b}), Differenz {diff}.")
    return Befund("arithmetik", Schwere.OK, "Rechnung rechnerisch stimmig.")


def pruefe_pflichtfelder(daten: dict, pflicht: tuple[str, ...]) -> list[Befund]:
    """Meldet jedes fehlende/leere Pflichtfeld als FEHLER."""
    befunde = []
    for feld in pflicht:
        wert = daten.get(feld)
        if wert in (None, "", []):
            befunde.append(Befund(feld, Schwere.FEHLER, f"Pflichtfeld '{feld}' fehlt."))
    if not befunde:
        befunde.append(Befund("pflichtfelder", Schwere.OK, "Alle Pflichtfelder vorhanden."))
    return befunde


def dubletten_schluessel(beleg: dict) -> str:
    """Stabiler Schluessel aus Rechnungsnr + Betrag + Datum + Partner (Dublettencheck)."""
    nr = str(beleg.get("rechnungsnummer") or beleg.get("nummer") or "").strip().lower()
    betrag = str(beleg.get("brutto") or beleg.get("betrag") or beleg.get("summe") or "").strip()
    datum = str(beleg.get("datum") or beleg.get("date") or "")[:10]
    partner = str(beleg.get("lieferant") or beleg.get("haendler")
                  or beleg.get("kunde") or "").strip().lower()
    return f"{nr}|{betrag}|{datum}|{partner}"


def ist_dublette(beleg: dict, bekannt: set[str]) -> bool:
    """True, wenn der Beleg-Schluessel bereits in ``bekannt`` ist."""
    return dubletten_schluessel(beleg) in bekannt
