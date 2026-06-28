"""Lexware Office Public API — Client mit Rate-Limit-Backoff.

Realitaet (Abschnitt 3 der Spezifikation):
  * nur EUR; Steuersaetze 0/5/7/16/19 %,
  * Rate-Limit 2 req/s -> HTTP 429 -> Backoff/Queue,
  * Belege werden per API default als DRAFT angelegt (kein Auto-Finalize),
  * API-Key laeuft ab -> erneuern.

Dieser Client legt Belege bewusst als Draft an (``finalize=False`` per Default) —
die Festschreibung bleibt ein menschlicher, freigabepflichtiger Schritt.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable, Optional

from ..models import ERLAUBTE_UST_SAETZE
from ..util.http import http_json, HttpError


@dataclass
class RateLimiter:
    """Einfacher Mindestabstand-Limiter (Default 2 req/s = 0.5 s Abstand)."""

    max_pro_sekunde: float = 2.0
    _last: Optional[float] = None
    _now: Callable[[], float] = time.monotonic
    _sleep: Callable[[float], None] = time.sleep

    def warte(self) -> None:
        if self.max_pro_sekunde <= 0:
            return
        min_abstand = 1.0 / self.max_pro_sekunde
        jetzt = self._now()
        if self._last is not None:
            delta = jetzt - self._last
            if delta < min_abstand:
                self._sleep(min_abstand - delta)
        self._last = self._now()


@dataclass
class LexwareClient:
    api_key: str
    base_url: str = "https://api.lexoffice.io/v1"
    finalize_belege: bool = False
    rate_limiter: RateLimiter = field(default_factory=RateLimiter)
    max_retries: int = 4

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json", "Accept": "application/json"}

    def _request(self, method: str, pfad: str, payload: Optional[dict] = None) -> dict:
        """Request mit Rate-Limit-Wartung und 429-Backoff (exponentiell)."""
        url = f"{self.base_url}{pfad}"
        versuch = 0
        while True:
            self.rate_limiter.warte()
            try:
                return http_json(url, method=method, payload=payload, headers=self._headers())
            except HttpError as exc:
                if exc.status == 429 and versuch < self.max_retries:
                    wartezeit = 2 ** versuch  # 1, 2, 4, 8 s
                    time.sleep(wartezeit)
                    versuch += 1
                    continue
                raise

    # ------------------------------------------------------------------ #
    def ping(self) -> dict:
        """Profil abrufen — verifiziert API-Key und Erreichbarkeit."""
        return self._request("GET", "/profile")

    def validiere_ust_satz(self, satz: Decimal) -> None:
        if Decimal(satz) not in ERLAUBTE_UST_SAETZE:
            raise ValueError(
                f"USt-Satz {satz}% in Lexware nicht zulaessig "
                f"(erlaubt: {', '.join(str(s) for s in ERLAUBTE_UST_SAETZE)})")

    def erstelle_ausgabe_beleg(
        self, *, datum: str, betrag_netto: Decimal, ust_satz: Decimal,
        kategorie_id: str, beschreibung: str = "",
    ) -> dict:
        """Legt einen Ausgabe-Beleg (Voucher) an — als DRAFT, sofern nicht finalisiert.

        ``kategorie_id`` ist die Lexware-Kategorie-UUID (z. B. Wareneinkauf). Der
        Aufrufer ist fuer korrekte Kategorien verantwortlich.
        """
        self.validiere_ust_satz(ust_satz)
        payload = {
            "type": "expense",
            "voucherDate": datum,
            "totalPrice": {"currency": "EUR"},
            "voucherItems": [{
                "amount": float(betrag_netto),
                "taxRatePercent": float(ust_satz),
                "categoryId": kategorie_id,
            }],
            "remark": beschreibung,
        }
        ergebnis = self._request("POST", "/vouchers", payload)
        if self.finalize_belege:
            # Bewusst NICHT automatisch: Festschreibung erfordert menschliche Freigabe.
            raise RuntimeError(
                "Auto-Finalize deaktiviert: Festschreibung ist freigabepflichtig.")
        return ergebnis
