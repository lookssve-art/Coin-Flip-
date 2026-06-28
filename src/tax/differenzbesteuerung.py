"""Differenzbesteuerung nach § 25a UStG.

Besteuert wird nur die Marge (Verkauf - Einkauf), typisch bei Ankauf von
Privatpersonen ohne Vorsteuer (viele Pokemon-/One-Piece-Karten). USt darf NICHT
offen ausgewiesen werden. Die im Marge-Betrag enthaltene USt wird herausgerechnet.

Zwei Methoden:
  * Einzeldifferenz  — pro Artikel.
  * Gesamtdifferenz  — Summe je Besteuerungszeitraum, nur fuer Einzelposten <= 750 EUR.

Wichtig: negative Margen (Verlustverkauf) erzeugen KEINE negative USt — die
Bemessungsgrundlage des betroffenen Vorgangs ist 0 (keine Verrechnung ueber die
Einzeldifferenz hinaus).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

GESAMTDIFFERENZ_GRENZE_EUR = Decimal("750")
_CENT = Decimal("0.01")


def _round(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


@dataclass
class MargenErgebnis:
    verkauf: Decimal
    einkauf: Decimal
    marge: Decimal              # Bemessungsgrundlage inkl. USt (>= 0)
    ust_satz: Decimal
    ust_betrag: Decimal         # aus der Marge herausgerechnet
    netto_marge: Decimal        # Marge ohne USt
    hinweis: str = ""


def einzeldifferenz(verkauf: Decimal, einkauf: Decimal,
                    ust_satz: Decimal = Decimal("19")) -> MargenErgebnis:
    """Marge eines einzelnen Artikels nach § 25a (Einzeldifferenz)."""
    verkauf = Decimal(verkauf)
    einkauf = Decimal(einkauf)
    roh_marge = verkauf - einkauf
    hinweis = ""
    if roh_marge <= 0:
        # Verlust/Null -> keine USt, Bemessungsgrundlage 0.
        return MargenErgebnis(verkauf, einkauf, Decimal("0"), ust_satz,
                              Decimal("0"), Decimal("0"),
                              hinweis="Marge <= 0: Bemessungsgrundlage 0, keine USt.")
    # USt ist in der Brutto-Marge enthalten: netto = marge / (1 + satz/100)
    faktor = Decimal("1") + ust_satz / Decimal("100")
    netto = _round(roh_marge / faktor)
    ust = _round(roh_marge - netto)
    return MargenErgebnis(verkauf, einkauf, _round(roh_marge), ust_satz, ust, netto, hinweis)


def gesamtdifferenz(posten: list[tuple[Decimal, Decimal]],
                    ust_satz: Decimal = Decimal("19")) -> MargenErgebnis:
    """Gesamtdifferenz ueber mehrere Posten (je Einzelposten <= 750 EUR).

    ``posten`` ist eine Liste von (verkauf, einkauf)-Tupeln. Posten ueber der
    750-EUR-Grenze werden nicht stillschweigend einbezogen, sondern als Hinweis
    markiert (sie sind einzeln per Einzeldifferenz zu behandeln).
    """
    summe_verkauf = Decimal("0")
    summe_einkauf = Decimal("0")
    uebergrenze = 0
    for verkauf, einkauf in posten:
        verkauf = Decimal(verkauf)
        einkauf = Decimal(einkauf)
        if verkauf > GESAMTDIFFERENZ_GRENZE_EUR or einkauf > GESAMTDIFFERENZ_GRENZE_EUR:
            uebergrenze += 1
            continue
        summe_verkauf += verkauf
        summe_einkauf += einkauf

    roh_marge = summe_verkauf - summe_einkauf
    hinweis = ""
    if uebergrenze:
        hinweis = (f"{uebergrenze} Posten > 750 EUR ausgeschlossen — "
                   f"einzeln per Einzeldifferenz behandeln.")
    if roh_marge <= 0:
        return MargenErgebnis(summe_verkauf, summe_einkauf, Decimal("0"), ust_satz,
                              Decimal("0"), Decimal("0"),
                              hinweis=(hinweis + " Gesamtmarge <= 0: keine USt.").strip())
    faktor = Decimal("1") + ust_satz / Decimal("100")
    netto = _round(roh_marge / faktor)
    ust = _round(roh_marge - netto)
    return MargenErgebnis(summe_verkauf, summe_einkauf, _round(roh_marge), ust_satz,
                          ust, netto, hinweis)
