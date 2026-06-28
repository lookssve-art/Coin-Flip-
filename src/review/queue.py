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
    """Review-Queue, optional JSON-persistent.

    Mit ``path`` wird die Queue ueber Prozesse geteilt (Pipeline schreibt,
    Telegram-Bot liest/loest auf). Ohne ``path`` rein im Speicher (wie bisher).
    Doppelte offene Faelle (gleicher Grund + Bezug) werden nicht erneut angelegt,
    damit wiederholte ``sync``-Laeufe die Queue nicht aufblaehen.
    """

    def __init__(self, path: Optional[str] = None):
        self.path = path
        self._items: dict[str, ReviewItem] = {}
        self._counter = itertools.count(1)
        if path:
            self._load()

    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        import json
        import os
        if not self.path or not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        max_n = 0
        for d in data:
            item = ReviewItem(
                id=d["id"], grund=d["grund"], bezug=d["bezug"],
                status=ReviewStatus(d.get("status", "review_required")),
                erstellt=d.get("erstellt", ""), aufgeloest_von=d.get("aufgeloest_von"))
            self._items[item.id] = item
            try:
                max_n = max(max_n, int(item.id.split("-")[-1]))
            except ValueError:
                pass
        self._counter = itertools.count(max_n + 1)

    def reload(self) -> None:
        """Liest den persistenten Store neu (Bot sieht Pipeline-Aenderungen)."""
        if not self.path:
            return
        self._items = {}
        self._load()

    def _save(self) -> None:
        if not self.path:
            return
        import json
        import os
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        data = [{"id": i.id, "grund": i.grund, "bezug": i.bezug,
                 "status": i.status.value, "erstellt": i.erstellt,
                 "aufgeloest_von": i.aufgeloest_von} for i in self._items.values()]
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    # ------------------------------------------------------------------ #
    def add(self, grund: str, bezug: str) -> ReviewItem:
        # Idempotenz: bestehenden offenen Fall (Grund+Bezug) wiederverwenden.
        for i in self._items.values():
            if (i.status == ReviewStatus.REVIEW_REQUIRED
                    and i.grund == grund and i.bezug == bezug):
                return i
        item_id = f"REV-{next(self._counter):05d}"
        item = ReviewItem(id=item_id, grund=grund, bezug=bezug)
        self._items[item_id] = item
        self._save()
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
        self._save()
        return item
