"""Datenmodelle fuer Rechnungen (Kleinunternehmer §19 / optional Regelbesteuerung)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


def _q(betrag: Decimal) -> Decimal:
    return Decimal(betrag).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class Absender:
    """Pflichtangaben des Rechnungsstellers (§14 UStG)."""
    name: str = ""
    strasse: str = ""
    plz: str = ""
    ort: str = ""
    land: str = "DE"
    steuernummer: str = ""        # entweder Steuernummer ODER USt-IdNr Pflicht
    ust_id: str = ""
    email: str = ""
    telefon: str = ""
    iban: str = ""
    bic: str = ""

    def vollstaendig(self) -> list[str]:
        """Liste fehlender Pflichtfelder (leer = ok)."""
        fehlt = []
        if not self.name:
            fehlt.append("name")
        if not (self.strasse and self.plz and self.ort):
            fehlt.append("anschrift")
        if not (self.steuernummer or self.ust_id):
            fehlt.append("steuernummer_oder_ust_id")
        return fehlt


@dataclass
class Empfaenger:
    name: str = ""
    strasse: str = ""
    plz: str = ""
    ort: str = ""
    land: str = "DE"

    @property
    def anzeige(self) -> str:
        return self.name or "Endkunde"


@dataclass
class Position:
    bezeichnung: str
    menge: Decimal = Decimal("1")
    einzelpreis: Decimal = Decimal("0")     # brutto = netto (Kleinunternehmer)
    einheit: str = "Stück"

    @property
    def gesamt(self) -> Decimal:
        return _q(self.menge * self.einzelpreis)


@dataclass
class Rechnung:
    nummer: str
    datum: date
    empfaenger: Empfaenger
    positionen: list[Position] = field(default_factory=list)
    absender: Absender = field(default_factory=Absender)
    leistungsdatum: date | None = None
    kleinunternehmer: bool = True
    kleinunternehmer_hinweis: str = (
        "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet (Kleinunternehmer).")
    einleitung: str = ""
    bemerkung: str = ""
    bestell_referenz: str = ""              # eBay Order/Transaction-ID (Nachvollziehbarkeit)

    @property
    def summe(self) -> Decimal:
        return _q(sum((p.gesamt for p in self.positionen), Decimal("0")))

    def als_dict(self) -> dict:
        """Serialisierbarer Snapshot (GoBD-Archiv)."""
        return {
            "nummer": self.nummer,
            "datum": self.datum.isoformat(),
            "leistungsdatum": (self.leistungsdatum or self.datum).isoformat(),
            "kleinunternehmer": self.kleinunternehmer,
            "bestell_referenz": self.bestell_referenz,
            "empfaenger": {
                "name": self.empfaenger.name, "strasse": self.empfaenger.strasse,
                "plz": self.empfaenger.plz, "ort": self.empfaenger.ort,
                "land": self.empfaenger.land,
            },
            "absender": {
                "name": self.absender.name, "strasse": self.absender.strasse,
                "plz": self.absender.plz, "ort": self.absender.ort,
                "land": self.absender.land, "steuernummer": self.absender.steuernummer,
                "ust_id": self.absender.ust_id,
            },
            "positionen": [
                {"bezeichnung": p.bezeichnung, "menge": str(p.menge),
                 "einheit": p.einheit, "einzelpreis": str(_q(p.einzelpreis)),
                 "gesamt": str(p.gesamt)}
                for p in self.positionen
            ],
            "summe": str(self.summe),
        }
