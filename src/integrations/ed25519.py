"""Reines Python Ed25519 (RFC 8032) — nur Signieren, keine Fremdpakete.

eBay verlangt fuer die Finances-API digitale Signaturen (RFC 9421) mit einem
Ed25519-Schluessel. Das Standardpaket dafuer waere ``cryptography``/PyNaCl; um
die Stdlib-only-Zusage des Kerns zu halten, ist hier die Referenz-Implementierung
aus RFC 8032 / D. J. Bernstein vendored (langsam, aber korrekt — pro Signatur
nur wenige Skalarmultiplikationen, das genuegt fuer Buchhaltungs-Calls).

Getestet gegen die offiziellen RFC-8032-Testvektoren (siehe tests/).
"""

from __future__ import annotations

import base64
import hashlib

_P = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493  # Gruppenordnung
_D = (-121665 * pow(121666, _P - 2, _P)) % _P
_I = pow(2, (_P - 1) // 4, _P)


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def _sha512_int(data: bytes) -> int:
    return int.from_bytes(_sha512(data), "little")


def _inv(x: int) -> int:
    return pow(x, _P - 2, _P)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(_D * y * y + 1) % _P
    x = pow(xx, (_P + 3) // 8, _P)
    if (x * x - xx) % _P != 0:
        x = (x * _I) % _P
    if x % 2 != 0:
        x = _P - x
    return x


_BY = 4 * _inv(5) % _P
_BX = _xrecover(_BY)
_B = (_BX % _P, _BY % _P)


def _edwards_add(p1, p2):
    x1, y1 = p1
    x2, y2 = p2
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + _D * x1 * x2 * y1 * y2) % _P
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - _D * x1 * x2 * y1 * y2) % _P
    return (x3 % _P, y3 % _P)


def _scalarmult(point, e: int):
    if e == 0:
        return (0, 1)
    q = _scalarmult(point, e // 2)
    q = _edwards_add(q, q)
    if e & 1:
        q = _edwards_add(q, point)
    return q


def _encodeint(y: int) -> bytes:
    return y.to_bytes(32, "little")


def _encodepoint(point) -> bytes:
    x, y = point
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _bit(h: bytes, i: int) -> int:
    return (h[i // 8] >> (i % 8)) & 1


def _clamp_scalar(h: bytes) -> int:
    return 2 ** 254 + sum(2 ** i * _bit(h, i) for i in range(3, 254))


def public_key(seed: bytes) -> bytes:
    """Leitet den 32-Byte Public Key aus dem 32-Byte Seed ab (fuer Self-Test)."""
    h = _sha512(seed)
    a = _clamp_scalar(h)
    return _encodepoint(_scalarmult(_B, a))


def sign(message: bytes, seed: bytes) -> bytes:
    """Signiert ``message`` mit dem 32-Byte Seed -> 64-Byte Signatur."""
    if len(seed) != 32:
        raise ValueError("Ed25519-Seed muss genau 32 Byte lang sein.")
    h = _sha512(seed)
    a = _clamp_scalar(h)
    pk = _encodepoint(_scalarmult(_B, a))
    r = _sha512_int(h[32:64] + message)
    rr = _scalarmult(_B, r)
    enc_r = _encodepoint(rr)
    k = _sha512_int(enc_r + pk + message)
    s = (r + k * a) % _L
    return enc_r + _encodeint(s)


def seed_from_pkcs8(b64_or_der) -> bytes:
    """Extrahiert den 32-Byte Seed aus einem PKCS#8-Ed25519-Private-Key.

    eBays Key-Management gibt den Private Key als Base64 der PKCS#8-DER-Struktur
    zurueck. Bei Ed25519 ist der Seed die letzten 32 Byte (fester OID-Prefix
    ``302e020100300506032b657004220420``). Akzeptiert Base64-String oder Bytes.
    """
    der = b64_or_der if isinstance(b64_or_der, (bytes, bytearray)) else base64.b64decode(b64_or_der)
    if len(der) < 32:
        raise ValueError("Ungueltiger PKCS#8-Ed25519-Key (zu kurz).")
    return bytes(der[-32:])
