"""Review-Queue (Human-in-the-Loop).

Sammelt alle ``REVIEW_REQUIRED``-Faelle. Eine Buchung darf nicht gegen eine offene
Review-Markierung "durchgewunken" werden (Abschnitt 10). Die Aufloesung erfolgt
durch einen Menschen und wird im Audit-Log protokolliert.
"""

from __future__ import annotations

import itertools
from decimal import Decimal
from typing import Optional

from ..models import ReviewItem, ReviewStatus


# Standard-Ausloeser fuer REVIEW_REQUIRED (Abschnitt 8 der Spezifikation).
def pruefe_review_trigger(
    *,
    differenz_einkaufsbeleg_unklar: bool = False,
    schwelle_naht: bool = False,
    gemischt_privat_geschaeftlich: bool = False,
    reverse_charge_ohne_ustid: bool = False,
    import_einfuhrumsatzsteuer: bool = False,
    erechnung_fehlerhaft: bool = False,
    beleg_bank_differenz: bool = False,
    betrag_brutto: Decimal = Decimal("0"),
    betragsschwelle: Decimal = Decimal("2000"),
) -> list[str]:
    """Gibt die Liste der zutreffenden Review-Gruende zurueck (leer = ok)."""
    gruende: list[str] = []
    if differenz_einkaufsbeleg_unklar:
        gruende.append("Differenzbesteuerung mit unklarem Einkaufsbeleg")
    if schwelle_naht:
        gruende.append("Annaeherung an Schwelle 25k/100k/10k")
    if gemischt_privat_geschaeftlich:
        gruende.append("Privat/geschaeftlich gemischte Ausgabe")
    if reverse_charge_ohne_ustid:
        gruende.append("Reverse-Charge / EU-B2B mit fehlender/ungueltiger USt-IdNr")
    if import_einfuhrumsatzsteuer:
        gruende.append("Import + Einfuhrumsatzsteuer")
    if erechnung_fehlerhaft:
        gruende.append("E-Rechnung mit Format- oder Geschaeftsregelfehler")
    if beleg_bank_differenz:
        gruende.append("Beleg <-> Bank Betragsdifferenz")
    if Decimal(betrag_brutto) > betragsschwelle:
        gruende.append(f"Buchung > Betragsschwelle ({betragsschwelle} EUR)")
    return gruende


class ReviewQueue:
    def __init__(self):
        self._items: dict[str, ReviewItem] = {}
        self._counter = itertools.count(1)

    def add(self, grund: str, bezug: str) -> ReviewItem:
        item_id = f"REV-{next(self._counter):05d}"
        item = ReviewItem(id=item_id, grund=grund, bezug=bezug)
        self._items[item_id] = item
        return item

    def add_many(self, gruende: list[str], bezug: str) -> list[ReviewItem]:
        return [self.add(g, bezug) for g in gruende]

    def offen(self) -> list[ReviewItem]:
        return [i for i in self._items.values() if i.status == ReviewStatus.REVIEW_REQUIRED]

    def hat_offene(self, bezug: str) -> bool:
        """True, wenn fuer ``bezug`` eine offene Review existiert (Buchung blockiert)."""
        return any(i.bezug == bezug and i.status == ReviewStatus.REVIEW_REQUIRED
                   for i in self._items.values())

    def aufloesen(self, item_id: str, *, freigeben: bool, von: str) -> Optional[ReviewItem]:
        item = self._items.get(item_id)
        if item is None:
            return None
        item.status = ReviewStatus.APPROVED if freigeben else ReviewStatus.REJECTED
        item.aufgeloest_von = von
        return item
