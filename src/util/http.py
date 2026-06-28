"""Schlanker JSON-HTTP-Client auf urllib-Basis (keine externe Abhaengigkeit).

Respektiert die Proxy-Umgebung (HTTPS_PROXY) und ein optionales CA-Bundle
(Umgebungsvariable ``SSL_CERT_FILE`` oder das ccr-Bundle), damit Aufrufe in
abgesicherten Ausfuehrungsumgebungen ohne Zusatzpakete funktionieren.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

_CCR_BUNDLE = "/root/.ccr/ca-bundle.crt"


class HttpError(RuntimeError):
    def __init__(self, status: int, body: str):
        super().__init__(f"HTTP {status}: {body[:300]}")
        self.status = status
        self.body = body


def _ssl_context() -> ssl.SSLContext:
    cafile = os.environ.get("SSL_CERT_FILE")
    if not cafile and os.path.exists(_CCR_BUNDLE):
        cafile = _CCR_BUNDLE
    if cafile and os.path.exists(cafile):
        return ssl.create_default_context(cafile=cafile)
    return ssl.create_default_context()


def http_json(
    url: str,
    *,
    method: str = "GET",
    payload: Optional[dict] = None,
    headers: Optional[dict] = None,
    timeout: float = 30.0,
) -> dict:
    """Fuehrt einen JSON-Request aus und gibt das geparste JSON zurueck.

    Wirft ``HttpError`` bei Status >= 400 (mit Body), ``urllib.error.URLError`` bei
    Netzwerk-/TLS-Fehlern.
    """
    data = None
    hdrs = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    if headers:
        hdrs.update(headers)

    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise HttpError(exc.code, body) from exc


def post_form(
    url: str,
    form: dict,
    *,
    headers: Optional[dict] = None,
    timeout: float = 30.0,
) -> dict:
    """POST mit ``application/x-www-form-urlencoded`` Body, JSON-Antwort.

    Fuer OAuth-Token-Endpunkte (z. B. eBay), die Form-Encoding und Basic-Auth
    erwarten. Wirft ``HttpError`` bei Status >= 400.
    """
    data = urllib.parse.urlencode(form).encode("utf-8")
    hdrs = {"Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise HttpError(exc.code, body) from exc
