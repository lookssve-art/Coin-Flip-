"""Fortlaufende, eindeutige Rechnungsnummern (§14 Abs. 4 Nr. 4 UStG).

Persistenter Zaehler in einer JSON-Datei. Schema:
  * mit Jahr:  ``{prefix}{JAHR}-{lfd:04d}``   z. B. ``2026-0001`` / ``RE-2026-0001``
  * ohne Jahr: ``{prefix}{lfd:04d}``           z. B. ``RE-0001`` / ``1001``

Der Zaehler ist monoton; bei Jahreswechsel beginnt die laufende Nummer (mit Jahr)
wieder bei der Startzahl. Vergebene Nummern werden NICHT wiederverwendet.
"""

from __future__ import annotations

import contextlib
import json
import os
from dataclasses import dataclass

try:
    import fcntl  # POSIX (macOS/Linux) — Cross-Prozess-Lock fuer die Nummernvergabe
except ImportError:  # pragma: no cover - Windows
    fcntl = None


@contextlib.contextmanager
def _dateisperre(pfad: str):
    """Serialisiert die Nummernvergabe ueber Prozesse hinweg (flock auf Lockdatei)."""
    if not pfad or fcntl is None:
        yield
        return
    os.makedirs(os.path.dirname(pfad) or ".", exist_ok=True)
    lock = open(pfad + ".lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


@dataclass
class Nummernkreis:
    pfad: str
    prefix: str = ""
    mit_jahr: bool = True
    start: int = 1
    stellen: int = 4

    def _laden(self) -> dict:
        if self.pfad and os.path.exists(self.pfad):
            try:
                with open(self.pfad, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _speichern(self, daten: dict) -> None:
        if not self.pfad:
            return
        os.makedirs(os.path.dirname(self.pfad) or ".", exist_ok=True)
        with open(self.pfad, "w", encoding="utf-8") as fh:
            json.dump(daten, fh, ensure_ascii=False, indent=2)

    def naechste(self, jahr: int) -> str:
        """Vergibt die naechste Nummer fuer ``jahr`` und persistiert den Stand.

        Cross-Prozess-gesperrt (flock), damit parallele Laeufe (serve + Telegram)
        keine doppelte Rechnungsnummer vergeben (§14 Abs. 4 Nr. 4 UStG)."""
        with _dateisperre(self.pfad):
            daten = self._laden()
            if self.mit_jahr:
                schluessel = str(jahr)
                letzte = int(daten.get(schluessel, self.start - 1))
                lfd = max(letzte + 1, self.start)
                daten[schluessel] = lfd
                self._speichern(daten)
                return f"{self.prefix}{jahr}-{lfd:0{self.stellen}d}"
            letzte = int(daten.get("global", self.start - 1))
            lfd = max(letzte + 1, self.start)
            daten["global"] = lfd
            self._speichern(daten)
            return f"{self.prefix}{lfd:0{self.stellen}d}"

    def vorschau(self, jahr: int) -> str:
        """Naechste Nummer OHNE den Zaehler zu erhoehen (z. B. fuer Dry-Runs)."""
        daten = self._laden()
        if self.mit_jahr:
            letzte = int(daten.get(str(jahr), self.start - 1))
            lfd = max(letzte + 1, self.start)
            return f"{self.prefix}{jahr}-{lfd:0{self.stellen}d}"
        letzte = int(daten.get("global", self.start - 1))
        lfd = max(letzte + 1, self.start)
        return f"{self.prefix}{lfd:0{self.stellen}d}"
