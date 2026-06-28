"""Lexware-Office-Sync: Belege -> Draft-Vouchers (live).

Nimmt verarbeitete ``Receipt``s und legt sie als Ausgabe-Belege (Vouchers) in
Lexware Office an — bewusst als DRAFT (Festschreibung bleibt freigabepflichtig,
Abschnitt 4/10 der Spezifikation). Pro Beleg wird die interne Kategorie auf eine
Lexware-Kategorie-UUID gemappt (``kategorie_map`` aus der Konfiguration). Belege
ohne Mapping oder mit offener Review werden NICHT gepusht, sondern uebersprungen
und gemeldet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from ..export.lexware import LexwareClient
from ..models import Receipt
from ..review import ReviewQueue


@dataclass
class PushErgebnis:
    erstellt: list[str] = field(default_factory=list)       # Beleg-IDs erfolgreich
    uebersprungen: list[tuple] = field(default_factory=list)  # (beleg_id, grund)
    fehler: list[tuple] = field(default_factory=list)         # (beleg_id, fehlermeldung)


@dataclass
class LexwareSync:
    client: LexwareClient
    kategorie_map: dict                    # {"wareneinkauf": "<uuid>", ...}
    review_queue: Optional[ReviewQueue] = None

    def push_belege(self, receipts: list[Receipt]) -> PushErgebnis:
        """Legt fuer jeden geeigneten Beleg einen Draft-Voucher an."""
        ergebnis = PushErgebnis()
        for r in receipts:
            # Offene Review blockiert den Push (keine Buchung gegen REVIEW_REQUIRED).
            if self.review_queue is not None and self.review_queue.hat_offene(r.id):
                ergebnis.uebersprungen.append((r.id, "offene Review"))
                continue
            if r.vorsteuer_abzug == "unsicher":
                ergebnis.uebersprungen.append((r.id, "Vorsteuerabzug unsicher"))
                continue
            kategorie_id = self.kategorie_map.get(r.kategorie)
            if not kategorie_id:
                ergebnis.uebersprungen.append((r.id, f"keine Lexware-Kategorie fuer '{r.kategorie}'"))
                continue
            try:
                self.client.erstelle_ausgabe_beleg(
                    datum=r.datum.isoformat(),
                    betrag_netto=Decimal(r.netto),
                    ust_satz=Decimal(r.ust_satz),
                    kategorie_id=kategorie_id,
                    beschreibung=f"{r.haendler} ({r.kategorie}) — Beleg {r.id}",
                )
                ergebnis.erstellt.append(r.id)
            except Exception as exc:  # noqa: BLE001
                ergebnis.fehler.append((r.id, str(exc)))
        return ergebnis
