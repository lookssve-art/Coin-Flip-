"""Revisionssicherer Belegspeicher.

Legt Original-Belege (PDF, XML der E-Rechnung, Scan) inhaltsadressiert ab: der
Dateiname ist der SHA-256 des Inhalts. Eine erneute Ablage identischen Inhalts ist
idempotent; eine Aenderung erzeugt einen neuen Hash -> das Original bleibt
unveraendert erhalten (WORM-Prinzip). E-Rechnungen werden im strukturierten
Originalformat 8 Jahre archiviert (Ausdruck reicht nicht).
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass


@dataclass
class StoredObject:
    sha256: str
    pfad: str
    bytes_len: int
    bereits_vorhanden: bool


class ReceiptStore:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def _path_for(self, digest: str, suffix: str) -> str:
        # Zweistufige Faechertiefe vermeidet zu grosse Verzeichnisse.
        sub = os.path.join(self.base_dir, digest[:2])
        os.makedirs(sub, exist_ok=True)
        return os.path.join(sub, f"{digest}{suffix}")

    def store(self, content: bytes, suffix: str = "") -> StoredObject:
        """Legt ``content`` revisionssicher ab und gibt das StoredObject zurueck."""
        digest = hashlib.sha256(content).hexdigest()
        path = self._path_for(digest, suffix)
        if os.path.exists(path):
            return StoredObject(digest, path, len(content), bereits_vorhanden=True)
        # Schreiben + schreibgeschuetzt setzen (best effort WORM).
        with open(path, "wb") as fh:
            fh.write(content)
        try:
            os.chmod(path, 0o444)
        except OSError:
            pass
        return StoredObject(digest, path, len(content), bereits_vorhanden=False)

    def verify(self, digest: str, suffix: str = "") -> bool:
        """Prueft, ob die abgelegte Datei noch ihrem Inhalts-Hash entspricht."""
        path = self._path_for(digest, suffix)
        if not os.path.exists(path):
            return False
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest() == digest
