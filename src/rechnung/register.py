"""Idempotentes Rechnungsregister: pro Bestellung/Verkauf genau eine Rechnung.

Verhindert Doppel-Rechnungen bei wiederholten Laeufen und merkt sich, welche
Rechnung lokal gespeichert bzw. nach Lexware uebertragen wurde.
Schluessel = stabile Bestell-/Transaktions-ID (PlatformSale.id).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass
class RechnungsRegister:
    pfad: str
    _daten: dict | None = None

    def _laden(self) -> dict:
        if self._daten is None:
            if self.pfad and os.path.exists(self.pfad):
                try:
                    with open(self.pfad, "r", encoding="utf-8") as fh:
                        self._daten = json.load(fh)
                except (json.JSONDecodeError, OSError):
                    self._daten = {}
            else:
                self._daten = {}
        return self._daten

    def _speichern(self) -> None:
        if not self.pfad:
            return
        os.makedirs(os.path.dirname(self.pfad) or ".", exist_ok=True)
        with open(self.pfad, "w", encoding="utf-8") as fh:
            json.dump(self._daten or {}, fh, ensure_ascii=False, indent=2)

    def hat(self, bestell_id: str) -> bool:
        return bestell_id in self._laden()

    def eintrag(self, bestell_id: str) -> dict | None:
        return self._laden().get(bestell_id)

    def merke(self, bestell_id: str, nummer: str, **felder) -> None:
        daten = self._laden()
        eintrag = daten.get(bestell_id, {})
        eintrag.update({"nummer": nummer, **felder})
        daten[bestell_id] = eintrag
        self._speichern()

    def offene_lexware(self) -> list[str]:
        """Bestell-IDs mit lokaler Rechnung, aber ohne Lexware-Push."""
        return [bid for bid, e in self._laden().items() if not e.get("lexware_id")]

    def alle(self) -> dict:
        return dict(self._laden())
