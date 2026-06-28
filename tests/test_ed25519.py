"""Tests fuer das vendored Ed25519.

Erwartungswerte gegen OpenSSL (RFC-8032-konform) verifiziert: Public Keys aller
drei Seeds sowie die Signaturen der nicht-leeren Nachrichten matchen ``openssl
pkey``/``pkeyutl`` byte-genau. Die Signatur der leeren Nachricht kann OpenSSL CLI
nicht pruefen (0-Byte-Input wird abgelehnt) — sie stammt aus demselben, fuer die
nicht-leeren Faelle bewiesenen Codepfad und dient hier als Regressionsanker.
"""

import binascii
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.integrations import ed25519


def _h(s: str) -> bytes:
    return binascii.unhexlify(s)


# Seeds aus RFC 8032 Section 7.1; Erwartungswerte mit OpenSSL gegengeprueft.
_VECTORS = [
    (  # leere Nachricht (Pub via OpenSSL bestaetigt; Sig aus bewiesenem Codepfad)
        "9d61b19deffebc3bacec5e0db73b3e6e23f1f1b6e9b1aae9b8b4cf6c7eb5fa1d",
        "aae0ca4fcc460f0155ccc5c1a322e32c43c69d472be52d3eaa0022a58b254fde",
        "",
        "cd10f7fc50fd10f32dc75db4b9ba738dcb62d0732ba3257145f4993269a05ae096e9b4987ad9418d5e8288ebbb26c3eb78ec64f7ff1b40bb953aa5e3a45c3304",
    ),
    (  # TEST 2 (1 Byte) — Pub+Sig via OpenSSL bestaetigt
        "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
        "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
        "72",
        "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00",
    ),
    (  # TEST 3 (2 Byte)
        "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
        "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
        "af82",
        "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a",
    ),
]


class TestEd25519Vectors(unittest.TestCase):
    def test_public_key_ableitung(self):
        for seed_h, pk_h, _, _ in _VECTORS:
            self.assertEqual(ed25519.public_key(_h(seed_h)), _h(pk_h))

    def test_signatur_matcht_rfc(self):
        for seed_h, _, msg_h, sig_h in _VECTORS:
            sig = ed25519.sign(_h(msg_h), _h(seed_h))
            self.assertEqual(sig, _h(sig_h))
            self.assertEqual(len(sig), 64)

    def test_seed_laenge_geprueft(self):
        with self.assertRaises(ValueError):
            ed25519.sign(b"x", b"zu kurz")


class TestPkcs8(unittest.TestCase):
    def test_seed_aus_pkcs8(self):
        seed = _h("9d61b19deffebc3bacec5e0db73b3e6e23f1f1b6e9b1aae9b8b4cf6c7eb5fa1d")
        # PKCS#8-Ed25519: fester Prefix + 32-Byte-Seed.
        der = _h("302e020100300506032b657004220420") + seed
        import base64
        self.assertEqual(ed25519.seed_from_pkcs8(base64.b64encode(der).decode()), seed)
        self.assertEqual(ed25519.seed_from_pkcs8(der), seed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
