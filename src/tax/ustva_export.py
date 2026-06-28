"""USt-VA-Kennzahlen-Entwurf (ELSTER-Format) — VORBEREITUNG, keine Abgabe.

Bildet die zentralen Kennzahlen (Kz) der Umsatzsteuer-Voranmeldung aus den
Netto-Bemessungsgrundlagen und der Vorsteuer:

  Kz 81  Steuerpflichtige Umsaetze zum Steuersatz 19 % (Bemessungsgrundlage, netto)
  Kz 86  Steuerpflichtige Umsaetze zum Steuersatz  7 % (Bemessungsgrundlage, netto)
  Kz 66  Abziehbare Vorsteuerbetraege
  Kz 83  Verbleibende USt-Vorauszahlung / Ueberschuss (Zahllast)

Die § 25a-Marge (netto) gehoert in die 19 %-Bemessungsgrundlage (Kz 81) — die USt
wird offen NICHT ausgewiesen, fliesst aber in die Zahllast ein.

Bei Kleinunternehmern (§ 19) entfaellt die USt-VA — der Export meldet das explizit.
Liefert immer nur einen ENTWURF; die Abgabe via ELSTER bleibt menschlicher Schritt.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_DOWN

_EURO = Decimal("1")        # USt-VA-Kennzahlen werden in vollen Euro gemeldet (abgerundet)
_CENT = Decimal("0.01")


def _euro_ab(value: Decimal) -> Decimal:
    """Bemessungsgrundlagen werden auf volle Euro abgerundet (ELSTER-Konvention)."""
    return Decimal(value).quantize(_EURO, rounding=ROUND_DOWN)


def _cent(value: Decimal) -> Decimal:
    return Decimal(value).quantize(_CENT)


@dataclass
class UStVaKennzahlen:
    zeitraum: str
    kleinunternehmer: bool
    kennzahlen: dict = field(default_factory=dict)   # {"81": Decimal, "86": ..., "66": ..., "83": ...}
    ust_19: Decimal = Decimal("0")
    ust_7: Decimal = Decimal("0")
    zahllast: Decimal = Decimal("0")
    hinweise: list = field(default_factory=list)
    ist_entwurf: bool = True


def ustva_kennzahlen(
    zeitraum: str,
    *,
    kleinunternehmer: bool,
    netto_19: Decimal = Decimal("0"),
    netto_7: Decimal = Decimal("0"),
    vorsteuer: Decimal = Decimal("0"),
) -> UStVaKennzahlen:
    """Erzeugt den USt-VA-Kennzahlen-Entwurf."""
    res = UStVaKennzahlen(zeitraum=zeitraum, kleinunternehmer=kleinunternehmer)
    if kleinunternehmer:
        res.hinweise.append("Kleinunternehmer (§ 19 UStG): keine USt-VA abzugeben.")
        return res

    kz81 = _euro_ab(netto_19)
    kz86 = _euro_ab(netto_7)
    kz66 = _cent(vorsteuer)
    res.ust_19 = _cent(kz81 * Decimal("0.19"))
    res.ust_7 = _cent(kz86 * Decimal("0.07"))
    res.zahllast = _cent(res.ust_19 + res.ust_7 - kz66)
    res.kennzahlen = {"81": kz81, "86": kz86, "66": kz66, "83": res.zahllast}
    res.hinweise.append("Entwurf — Abgabe via ELSTER erfordert menschliche Freigabe.")
    return res


def schreibe_ustva_csv(pfad: str, k: UStVaKennzahlen) -> int:
    """Schreibt die Kennzahlen als CSV (Kennzahl;Bezeichnung;Wert). Rueckgabe: Zeilen."""
    bezeichnung = {
        "81": "Steuerpflichtige Umsaetze 19 % (Bemessungsgrundlage)",
        "86": "Steuerpflichtige Umsaetze 7 % (Bemessungsgrundlage)",
        "66": "Abziehbare Vorsteuerbetraege",
        "83": "Verbleibende USt-Vorauszahlung (Zahllast)",
    }
    with open(pfad, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["zeitraum", k.zeitraum])
        writer.writerow(["kennzahl", "bezeichnung", "wert_eur"])
        if k.kleinunternehmer:
            writer.writerow(["—", "Kleinunternehmer § 19 — keine USt-VA", "0"])
            return 1
        for kz in ("81", "86", "66", "83"):
            writer.writerow([kz, bezeichnung[kz], f"{k.kennzahlen[kz]}"])
    return 4
