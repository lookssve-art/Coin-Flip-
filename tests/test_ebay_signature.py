"""Tests fuer den eBay-Signaturheader-Builder (RFC 9421)."""

import base64
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.integrations import ebay_signature, ed25519

# Test-Seed (RFC-8032 Seed 2) — Pubkey/Sign sind anderswo gegen OpenSSL geprueft.
_SEED = bytes.fromhex("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb")
_JWE = "eyJhbGciOiJBMjU2R0NNS1cifQ.TESTJWE.payload"


def _rebuild_base(components, values, created):
    comp_list = " ".join(f'"{c}"' for c in components)
    sig_params = f"({comp_list});created={created}"
    lines = [f'"{c}": {values[c]}' for c in components]
    lines.append(f'"@signature-params": {sig_params}')
    return "\n".join(lines).encode("utf-8")


class TestContentDigest(unittest.TestCase):
    def test_format(self):
        cd = ebay_signature.content_digest(b'{"a":1}')
        self.assertTrue(cd.startswith("sha-256=:") and cd.endswith(":"))


class TestSignatureHeadersGet(unittest.TestCase):
    def setUp(self):
        self.h = ebay_signature.build_signature_headers(
            method="GET", path="/sell/finances/v1/transaction?limit=200",
            authority="apiz.ebay.com", jwe=_JWE, seed=_SEED, created=1700000000,
        )

    def test_keine_content_digest_ohne_body(self):
        self.assertNotIn("Content-Digest", self.h)

    def test_header_vorhanden(self):
        self.assertEqual(self.h["x-ebay-signature-key"], _JWE)
        self.assertTrue(self.h["Signature"].startswith("sig1=:"))
        self.assertIn("created=1700000000", self.h["Signature-Input"])
        self.assertIn('"x-ebay-signature-key" "@method" "@path" "@authority"',
                      self.h["Signature-Input"])

    def test_signatur_verifizierbar(self):
        # Signature-Base rekonstruieren und gegen die Public-Key-Ableitung pruefen.
        components = ["x-ebay-signature-key", "@method", "@path", "@authority"]
        values = {
            "x-ebay-signature-key": _JWE, "@method": "GET",
            "@path": "/sell/finances/v1/transaction?limit=200",
            "@authority": "apiz.ebay.com",
        }
        base = _rebuild_base(components, values, 1700000000)
        sig_b64 = self.h["Signature"][len("sig1=:"):-1]
        sig = base64.b64decode(sig_b64)
        # Selber Codepfad signiert die rekonstruierte Base identisch.
        self.assertEqual(sig, ed25519.sign(base, _SEED))


class TestSignatureHeadersPost(unittest.TestCase):
    def test_content_digest_in_komponenten(self):
        body = b'{"signingKeyCipher":"ED25519"}'
        h = ebay_signature.build_signature_headers(
            method="POST", path="/developer/key_management/v1/signing_key",
            authority="apiz.ebay.com", jwe=_JWE, seed=_SEED, created=1700000000,
            body=body,
        )
        self.assertIn("Content-Digest", h)
        self.assertEqual(h["Content-Digest"], ebay_signature.content_digest(body))
        self.assertTrue(h["Signature-Input"].startswith('sig1=("content-digest"'))


if __name__ == "__main__":
    unittest.main(verbosity=2)
