"""Schwellen-Monitoring mit Fruehwarnung (§ 19 UStG, OSS, GewSt).

Ueberwacht die drei kritischen Grenzen:
  * Kleinunternehmer Vorjahr   25.000 EUR netto
  * Kleinunternehmer laufend   100.000 EUR netto (harte Grenze, "Fallbeileffekt")
  * OSS-Fernverkauf            10.000 EUR netto (EU-weit; § 25a-Ware AUSGENOMMEN)

Loest ``REVIEW_REQUIRED`` aus, sobald ``warnung_ab_prozent`` einer Schwelle
erreicht ist — rechtzeitig, bevor die Grenze gerissen wird.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class SchwellenStatus:
    name: str
    aktuell: Decimal
    grenze: Decimal
    prozent: Decimal
    warnung: bool          # >= warnung_ab_prozent
    ueberschritten: bool
    hinweis: str = ""


@dataclass
class SchwellenMonitor:
    ku_vorjahr_grenze: Decimal = Decimal("25000")
    ku_laufend_grenze: Decimal = Decimal("100000")
    ku_erstjahr_grenze: Decimal = Decimal("25000")   # Gruendungsjahr: 25k-Kappe (§19 UStG 2025)
    oss_grenze: Decimal = Decimal("10000")
    warnung_ab_prozent: Decimal = Decimal("80")
    _warnungen: list[str] = field(default_factory=list)

    def _status(self, name: str, aktuell: Decimal, grenze: Decimal, hinweis: str = "") -> SchwellenStatus:
        aktuell = Decimal(aktuell)
        prozent = (aktuell / grenze * Decimal("100")) if grenze else Decimal("0")
        prozent = prozent.quantize(Decimal("0.1"))
        warnung = prozent >= self.warnung_ab_prozent
        ueberschritten = aktuell > grenze
        return SchwellenStatus(name, aktuell, grenze, prozent, warnung, ueberschritten, hinweis)

    def kleinunternehmer_vorjahr(self, netto_vorjahr: Decimal) -> SchwellenStatus:
        return self._status("KU Vorjahr (§19)", netto_vorjahr, self.ku_vorjahr_grenze,
                            "Bei Ueberschreitung entfaellt KU-Status im Folgejahr.")

    def kleinunternehmer_laufend(self, netto_laufend: Decimal) -> SchwellenStatus:
        return self._status("KU laufend (§19)", netto_laufend, self.ku_laufend_grenze,
                            "Harte Grenze: der Umsatz, mit dem 100k gerissen wird, ist bereits "
                            "voll regelbesteuert.")

    def kleinunternehmer_erstjahr(self, netto_laufend: Decimal) -> SchwellenStatus:
        """Gruendungsjahr: bindende Grenze ist 25.000 EUR (kein Vorjahr vorhanden).

        Bei Ueberschreitung entfaellt der KU-Status ab dem gerissen Umsatz —
        ab dann Regelbesteuerung."""
        return self._status("KU Gruendungsjahr (§19)", netto_laufend, self.ku_erstjahr_grenze,
                            "Gruendungsjahr-Kappe 25.000 EUR: bei Ueberschreitung entfaellt "
                            "der Kleinunternehmer-Status ab diesem Umsatz -> Regelbesteuerung.")

    def oss_fernverkauf(self, netto_eu_b2c_ohne_25a: Decimal) -> SchwellenStatus:
        return self._status("OSS-Fernverkauf", netto_eu_b2c_ohne_25a, self.oss_grenze,
                            "§ 25a-Ware ist aus dieser Berechnung auszunehmen.")

    def pruefe_alle(self, netto_vorjahr: Decimal, netto_laufend: Decimal,
                    netto_eu_b2c_ohne_25a: Decimal) -> list[SchwellenStatus]:
        """Liefert den Status aller drei Schwellen (fuer Dashboard/Review-Queue)."""
        return [
            self.kleinunternehmer_vorjahr(netto_vorjahr),
            self.kleinunternehmer_laufend(netto_laufend),
            self.oss_fernverkauf(netto_eu_b2c_ohne_25a),
        ]
