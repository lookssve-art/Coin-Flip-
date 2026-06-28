"""eBay Key-Management-API — Ed25519-Signaturschluessel erzeugen/abrufen.

Einmalig pro Konto: ``POST /developer/key_management/v1/signing_key`` mit einem
gewoehnlichen OAuth-Token (die Key-Erstellung selbst braucht KEINE Signatur).
eBay erzeugt das Schluesselpaar und gibt den Private Key GENAU EINMAL zurueck —
er muss sofort sicher gespeichert werden (hier: gitignored config.yaml).

Antwortfelder (relevant):
  * ``signingKeyId``   — Schluessel-ID
  * ``jwe``            — Wert fuer den ``x-ebay-signature-key``-Header
  * ``privateKey``     — PKCS#8-Base64 (nur jetzt sichtbar)
  * ``publicKey``      — SPKI-Base64
  * ``expirationTime`` — Ablauf (Unix-Sekunden)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..util.http import http_json

_KEY_MGMT_BASE = {
    "production": "https://apiz.ebay.com/developer/key_management/v1",
    "sandbox": "https://apiz.sandbox.ebay.com/developer/key_management/v1",
}


@dataclass
class SigningKey:
    signing_key_id: str
    jwe: str
    private_key: str = ""        # PKCS#8 Base64 — nur bei Erstellung gesetzt
    public_key: str = ""
    expiration_time: int = 0
    cipher: str = "ED25519"

    @classmethod
    def from_dict(cls, d: dict) -> "SigningKey":
        return cls(
            signing_key_id=d.get("signingKeyId", ""),
            jwe=d.get("jwe", ""),
            private_key=d.get("privateKey", ""),
            public_key=d.get("publicKey", ""),
            expiration_time=int(d.get("expirationTime", 0) or 0),
            cipher=d.get("signingKeyCipher", "ED25519"),
        )


@dataclass
class EbayKeyManagement:
    access_token: str
    environment: str = "production"
    _poster: Callable[..., dict] = field(default=http_json, repr=False)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def create_signing_key(self, cipher: str = "ED25519") -> SigningKey:
        """Erzeugt ein neues Ed25519-Signaturschluesselpaar (Private Key einmalig)."""
        base = _KEY_MGMT_BASE[self.environment]
        data = self._poster(
            f"{base}/signing_key",
            method="POST",
            payload={"signingKeyCipher": cipher},
            headers=self._headers(),
        )
        return SigningKey.from_dict(data)

    def get_signing_key(self, signing_key_id: str) -> SigningKey:
        """Liest Metadaten eines bestehenden Schluessels (ohne Private Key)."""
        base = _KEY_MGMT_BASE[self.environment]
        data = self._poster(f"{base}/signing_key/{signing_key_id}",
                            headers=self._headers())
        return SigningKey.from_dict(data)
