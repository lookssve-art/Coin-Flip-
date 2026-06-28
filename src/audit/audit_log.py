"""Append-only Audit-Log mit Hash-Verkettung.

GoBD verlangt Unveraenderbarkeit und Nachvollziehbarkeit. Jede Buchung/Aenderung
wird als JSONL-Zeile angehaengt; jeder Eintrag enthaelt den Hash seines Vorgaengers
(Blockchain-artige Kette). Eine nachtraegliche Manipulation einer Zeile bricht die
Kette und ist durch ``verify()`` erkennbar. Aenderungen erfolgen nur als neue
Korrektur-Eintraege, nie durch Ueberschreiben.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, Optional

GENESIS_HASH = "0" * 64


@dataclass
class AuditRecord:
    seq: int
    zeitstempel: str
    event: str
    payload: dict
    prev_hash: str
    hash: str


def _canonical(data: dict) -> str:
    """Stabile, sortierte JSON-Repraesentation fuer reproduzierbares Hashing."""
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _compute_hash(seq: int, zeitstempel: str, event: str, payload: dict, prev_hash: str) -> str:
    material = _canonical(
        {"seq": seq, "ts": zeitstempel, "event": event, "payload": payload, "prev": prev_hash}
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class AuditLog:
    """Dateibasierter append-only Log. Fuer den MVP ausreichend; Prod -> WORM-Storage."""

    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    # ------------------------------------------------------------------ #
    def _last(self) -> Optional[AuditRecord]:
        last = None
        for rec in self.read_all():
            last = rec
        return last

    def append(self, event: str, payload: dict) -> AuditRecord:
        """Haengt einen neuen Eintrag an und gibt ihn zurueck."""
        last = self._last()
        seq = (last.seq + 1) if last else 1
        prev_hash = last.hash if last else GENESIS_HASH
        ts = datetime.now().isoformat(timespec="seconds")
        h = _compute_hash(seq, ts, event, payload, prev_hash)
        rec = AuditRecord(seq=seq, zeitstempel=ts, event=event, payload=payload,
                          prev_hash=prev_hash, hash=h)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec.__dict__, ensure_ascii=False) + "\n")
        return rec

    def read_all(self) -> Iterator[AuditRecord]:
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                yield AuditRecord(**d)

    def verify(self) -> tuple[bool, Optional[int]]:
        """Prueft die Hash-Kette. Rueckgabe (ok, erste_fehlerhafte_seq)."""
        prev_hash = GENESIS_HASH
        expected_seq = 1
        for rec in self.read_all():
            if rec.seq != expected_seq or rec.prev_hash != prev_hash:
                return False, rec.seq
            recomputed = _compute_hash(rec.seq, rec.zeitstempel, rec.event,
                                       rec.payload, rec.prev_hash)
            if recomputed != rec.hash:
                return False, rec.seq
            prev_hash = rec.hash
            expected_seq += 1
        return True, None

    def count(self) -> int:
        return sum(1 for _ in self.read_all())
