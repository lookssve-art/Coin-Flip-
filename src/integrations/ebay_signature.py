"""eBay-Digital-Signatures: Signaturheader nach RFC 9421 bauen.

eBay weist Finances-Aufrufe ohne gueltige Signatur mit HTTP 403 / errorId 215001
("Missing x-ebay-signature-key header") ab. Jede signierte Anfrage braucht:

  * ``x-ebay-signature-key``  — das JWE aus dem Key-Management (Public-Key-Referenz)
  * ``Content-Digest``        — nur bei Body (POST/PUT): ``sha-256=:<base64>:``
  * ``Signature-Input``       — die signierten Komponenten + ``created``-Timestamp
  * ``Signature``             — Ed25519 ueber die Signature-Base, base64, ``sig1=:...:``

Die Signature-Base wird zeilenweise aus den Komponenten gebildet (genau in der
in ``Signature-Input`` gelisteten Reihenfolge), abgeschlossen mit
``@signature-params``. Reihenfolge laut eBay:
  mit Body : ("content-digest" "x-ebay-signature-key" "@method" "@path" "@authority")
  ohne Body: ("x-ebay-signature-key" "@method" "@path" "@authority")
"""

from __future__ import annotations

import base64
import hashlib

from . import ed25519


def content_digest(body: bytes) -> str:
    """``Content-Digest``-Header-Wert (SHA-256) fuer einen Request-Body."""
    digest = hashlib.sha256(body).digest()
    return "sha-256=:" + base64.b64encode(digest).decode("ascii") + ":"


def build_signature_headers(*, method: str, path: str, authority: str, jwe: str,
                            seed: bytes, created: int, body: bytes = b"") -> dict:
    """Erzeugt alle Signatur-Header fuer einen eBay-Request.

    ``path`` ist der Pfad inkl. Query (z. B. ``/sell/finances/v1/transaction?...``),
    ``authority`` der Host (z. B. ``apiz.ebay.com``), ``created`` ein Unix-Timestamp.
    """
    has_body = bool(body)
    components: list[str] = []
    headers: dict[str, str] = {"x-ebay-signature-key": jwe}

    if has_body:
        cd = content_digest(body)
        headers["Content-Digest"] = cd
        components.append("content-digest")
    components += ["x-ebay-signature-key", "@method", "@path", "@authority"]

    comp_list = " ".join(f'"{c}"' for c in components)
    sig_params = f"({comp_list});created={created}"

    values = {
        "content-digest": headers.get("Content-Digest", ""),
        "x-ebay-signature-key": jwe,
        "@method": method.upper(),
        "@path": path,
        "@authority": authority,
    }
    lines = [f'"{c}": {values[c]}' for c in components]
    lines.append(f'"@signature-params": {sig_params}')
    base = "\n".join(lines).encode("utf-8")

    signature = ed25519.sign(base, seed)
    headers["Signature-Input"] = f"sig1={sig_params}"
    headers["Signature"] = "sig1=:" + base64.b64encode(signature).decode("ascii") + ":"
    return headers
