"""EÜR-Übersicht (Einnahmen-Überschuss-Rechnung, § 4 Abs. 3 EStG).

Aggregiert Einnahmen (Verkaeufe) und Ausgaben (Belege je Kategorie) zu einer
Gewinnermittlung nach Ist-Prinzip — als Übersicht fuer den Steuerberater / die
Anlage EUR (Vorbereitung, keine Abgabe).

Methodik:
  * Kleinunternehmer (§ 19): Brutto = Netto (keine USt) -> Brutto-Betraege.
  * Regelbesteuerung: Netto-Betraege (USt laeuft ueber die USt-VA, Nettomethode).
Der Gewerbesteuer-Freibetrag (24.500 EUR Gewinn) wird zur Orientierung geprueft.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

_CENT = Decimal("0.01")


def _round(v: Decimal) -> Decimal:
    return Decimal(v).quantize(_CENT, rounding=ROUND_HALF_UP)


@dataclass
class EuerReport:
    zeitraum: str
    kleinunternehmer: bool
    einnahmen_gesamt: Decimal = Decimal("0")
    ausgaben_je_kategorie: dict = field(default_factory=dict)
    ausgaben_gesamt: Decimal = Decimal("0")
    gewinn: Decimal = Decimal("0")
    gewerbesteuer_freibetrag: Decimal = Decimal("24500")
    ueber_gewst_freibetrag: bool = False
    hinweise: list = field(default_factory=list)


def euer_uebersicht(
    sales: list, receipts: list, *,
    kleinunternehmer: bool, zeitraum: str,
    default_ust_satz: Decimal = Decimal("19"),
    gewst_freibetrag: Decimal = Decimal("24500"),
) -> EuerReport:
    """Erstellt die EÜR-Übersicht aus Verkaeufen + Belegen."""
    r = EuerReport(zeitraum=zeitraum, kleinunternehmer=kleinunternehmer,
                   gewerbesteuer_freibetrag=Decimal(gewst_freibetrag))
    faktor = Decimal("1") + Decimal(default_ust_satz) / Decimal("100")

    # Einnahmen.
    einnahmen = Decimal("0")
    for s in sales:
        brutto = Decimal(s.brutto)
        if brutto <= 0:
            continue
        einnahmen += brutto if kleinunternehmer else _round(brutto / faktor)
    r.einnahmen_gesamt = _round(einnahmen)

    # Ausgaben je Kategorie (Belege tragen brutto + netto).
    for beleg in receipts:
        betrag = Decimal(beleg.brutto) if kleinunternehmer else Decimal(beleg.netto or 0)
        kat = beleg.kategorie or "sonstiges"
        r.ausgaben_je_kategorie[kat] = r.ausgaben_je_kategorie.get(kat, Decimal("0")) + betrag
    r.ausgaben_je_kategorie = {k: _round(v) for k, v in r.ausgaben_je_kategorie.items()}
    r.ausgaben_gesamt = _round(sum(r.ausgaben_je_kategorie.values(), Decimal("0")))

    r.gewinn = _round(r.einnahmen_gesamt - r.ausgaben_gesamt)
    r.ueber_gewst_freibetrag = r.gewinn > r.gewerbesteuer_freibetrag
    if r.ueber_gewst_freibetrag:
        r.hinweise.append(
            f"Gewinn {r.gewinn} EUR ueber Gewerbesteuer-Freibetrag "
            f"({r.gewerbesteuer_freibetrag} EUR) — Gewerbesteuer beachten.")
    r.hinweise.append("Ist-Prinzip (Zufluss/Abfluss); Übersicht, keine Abgabe.")
    if not kleinunternehmer:
        r.hinweise.append("Regelbesteuerung: Netto-Betraege (USt ueber USt-VA).")
    return r


def schreibe_euer_csv(pfad: str, r: EuerReport) -> int:
    """Schreibt die EÜR-Übersicht als CSV. Rueckgabe: Anzahl Datenzeilen."""
    n = 0
    with open(pfad, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["EÜR-Übersicht", r.zeitraum])
        w.writerow(["position", "kategorie", "betrag_eur"])
        w.writerow(["Einnahmen", "gesamt", f"{r.einnahmen_gesamt}"]); n += 1
        for kat, betrag in sorted(r.ausgaben_je_kategorie.items()):
            w.writerow(["Ausgabe", kat, f"{betrag}"]); n += 1
        w.writerow(["Ausgaben", "gesamt", f"{r.ausgaben_gesamt}"]); n += 1
        w.writerow(["Gewinn", "", f"{r.gewinn}"]); n += 1
    return n
