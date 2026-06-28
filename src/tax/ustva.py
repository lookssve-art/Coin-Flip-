"""USt-Voranmeldung — VORBEREITUNG (kein ELSTER-Versand).

Aggregiert Umsatzsteuer (je Satz) und Vorsteuer zu einer Zahllast-Vorschau.
Liefert IMMER nur einen Entwurf; die Abgabe via ELSTER bleibt ein menschlicher,
freigabepflichtiger Schritt (Abschnitt 9/10 der Spezifikation).

Bei Kleinunternehmern (§ 19) entfaellt die USt-VA — der Report meldet dies
explizit, statt eine leere Zahllast vorzutaeuschen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

_CENT = Decimal("0.01")


@dataclass
class UStVaReport:
    zeitraum: str
    kleinunternehmer: bool
    umsatzsteuer_je_satz: dict = field(default_factory=dict)  # {"19": Decimal, ...}
    differenz_ust: Decimal = Decimal("0")     # USt aus § 25a-Margen
    vorsteuer: Decimal = Decimal("0")
    ust_gesamt: Decimal = Decimal("0")
    zahllast: Decimal = Decimal("0")
    hinweise: list[str] = field(default_factory=list)
    ist_entwurf: bool = True                  # niemals automatisch abgeben


def _round(v: Decimal) -> Decimal:
    return Decimal(v).quantize(_CENT, rounding=ROUND_HALF_UP)


def ustva_vorbereitung(
    zeitraum: str,
    *,
    kleinunternehmer: bool,
    umsatzsteuer_je_satz: dict[str, Decimal] | None = None,
    differenz_ust: Decimal = Decimal("0"),
    vorsteuer: Decimal = Decimal("0"),
) -> UStVaReport:
    """Erstellt den USt-VA-Entwurf fuer einen Zeitraum."""
    umsatzsteuer_je_satz = {k: Decimal(v) for k, v in (umsatzsteuer_je_satz or {}).items()}
    report = UStVaReport(zeitraum=zeitraum, kleinunternehmer=kleinunternehmer)

    if kleinunternehmer:
        report.hinweise.append(
            "Kleinunternehmer (§ 19 UStG): keine USt-VA abzugeben, kein Vorsteuerabzug. "
            "Report dient nur der internen Umsatzkontrolle."
        )
        if vorsteuer > 0:
            report.hinweise.append(
                "WARNUNG: Vorsteuer erfasst, aber KU-Status aktiv — kein Abzug moeglich. "
                "Pruefen, ob Option zur Regelbesteuerung sinnvoll ist."
            )
        return report

    report.umsatzsteuer_je_satz = {k: _round(v) for k, v in umsatzsteuer_je_satz.items()}
    report.differenz_ust = _round(differenz_ust)
    report.vorsteuer = _round(vorsteuer)
    report.ust_gesamt = _round(sum(report.umsatzsteuer_je_satz.values(), Decimal("0"))
                               + report.differenz_ust)
    report.zahllast = _round(report.ust_gesamt - report.vorsteuer)
    report.hinweise.append("Entwurf — Abgabe via ELSTER erfordert menschliche Freigabe.")
    return report
