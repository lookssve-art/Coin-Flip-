"""eBay OAuth2 (Authorization Code Grant) — gewerblich/Production.

Scriptet den Consent-Flow, der einen User-Access-Token + Refresh-Token liefert
(noetig fuer die Finances-/Fulfillment-APIs, die im Namen des Verkaeufers lesen):

  1. ``consent_url()``      -> URL, die der Inhaber im Browser bestaetigt.
  2. eBay leitet auf die RuName-Redirect-URL mit ``?code=...`` weiter.
  3. ``exchange_code(code)`` -> Access-Token (~2 h) + Refresh-Token (~18 Monate).
  4. ``refresh(refresh_token)`` -> neuer Access-Token, ohne erneutes Consent.

Der HTTP-Poster ist injizierbar, damit der Flow ohne Live-Netzwerk testbar ist.
Secrets (app_id/cert_id) kommen aus config.yaml (gitignored).
"""

from __future__ import annotations

import base64
import urllib.parse
from dataclasses import dataclass, field
from typing import Callable, Optional

from ..util.http import post_form

# Production-Endpunkte (gewerbliches Konto).
_AUTH_BASE = {
    "production": "https://auth.ebay.com/oauth2/authorize",
    "sandbox": "https://auth.sandbox.ebay.com/oauth2/authorize",
}
_TOKEN_URL = {
    "production": "https://api.ebay.com/identity/v1/oauth2/token",
    "sandbox": "https://api.sandbox.ebay.com/identity/v1/oauth2/token",
}

# Scopes fuer read-only Buchhaltung: Finances (Auszahlungen/Transaktionen) +
# Fulfillment (Bestellungen/Versand). Erweiterbar nach Bedarf.
DEFAULT_SCOPES = (
    "https://api.ebay.com/oauth/api_scope",
    "https://api.ebay.com/oauth/api_scope/sell.finances",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment.readonly",
)


@dataclass
class TokenResponse:
    access_token: str
    expires_in: int
    token_type: str = "User Access Token"
    refresh_token: Optional[str] = None
    refresh_token_expires_in: Optional[int] = None

    @classmethod
    def from_dict(cls, d: dict) -> "TokenResponse":
        return cls(
            access_token=d["access_token"],
            expires_in=int(d.get("expires_in", 0)),
            token_type=d.get("token_type", "User Access Token"),
            refresh_token=d.get("refresh_token"),
            refresh_token_expires_in=(int(d["refresh_token_expires_in"])
                                      if d.get("refresh_token_expires_in") else None),
        )


@dataclass
class EbayOAuth:
    app_id: str                         # Client ID
    cert_id: str                        # Client Secret
    ru_name: str = ""                   # RuName — nur fuer den initialen Consent noetig,
                                        # NICHT fuer den laufenden Refresh
    environment: str = "production"
    scopes: tuple = DEFAULT_SCOPES
    _poster: Callable[..., dict] = field(default=post_form, repr=False)

    def _basic_auth(self) -> str:
        raw = f"{self.app_id}:{self.cert_id}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("ascii")

    def consent_url(self, state: Optional[str] = None) -> str:
        """Baut die Consent-URL, die der Konto-Inhaber im Browser bestaetigt."""
        if not self.ru_name:
            raise ValueError("consent_url braucht einen ru_name (RuName).")
        params = {
            "client_id": self.app_id,
            "redirect_uri": self.ru_name,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "prompt": "login",
        }
        if state:
            params["state"] = state
        return f"{_AUTH_BASE[self.environment]}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code: str) -> TokenResponse:
        """Tauscht den Authorization-Code gegen Access- + Refresh-Token.

        eBay liefert den Code in der Redirect-URL URL-encodiert; wir dekodieren ihn,
        damit man die ganze ``code=...``-Angabe einfach hineinkopieren kann.
        """
        code = urllib.parse.unquote(code.strip())
        # Falls die ganze Redirect-URL eingefuegt wurde: nur den code-Parameter nehmen.
        if "code=" in code:
            code = code.split("code=", 1)[1].split("&", 1)[0]
            code = urllib.parse.unquote(code)
        data = self._poster(
            _TOKEN_URL[self.environment],
            {"grant_type": "authorization_code", "code": code, "redirect_uri": self.ru_name},
            headers={"Authorization": self._basic_auth()},
        )
        return TokenResponse.from_dict(data)

    def refresh(self, refresh_token: str) -> TokenResponse:
        """Holt einen neuen Access-Token via Refresh-Token (kein neues Consent)."""
        data = self._poster(
            _TOKEN_URL[self.environment],
            {"grant_type": "refresh_token", "refresh_token": refresh_token,
             "scope": " ".join(self.scopes)},
            headers={"Authorization": self._basic_auth()},
        )
        return TokenResponse.from_dict(data)
