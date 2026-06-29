"""Lexware Office API — Rechnungen anlegen (read+write) und PDF abrufen.

Legt eine ``Rechnung`` ueber ``POST /v1/invoices`` an: per Default als Entwurf,
mit ``finalize=true`` festgeschrieben (status ``open``, finale Nummer/PDF).
Fuer Kleinunternehmer wird ``taxConditions.taxType = "vatfree"`` gesetzt
(USt-frei, keine referenzierte Kontakt-ID noetig) und der §19-Hinweis als
``taxTypeNote``/``remark`` mitgegeben.

PDF: ``GET /invoices/{id}/document`` -> ``documentFileId`` -> ``GET /files/{id}``.

Der HTTP-Poster/Getter ist injizierbar (offline testbar). Schreibend nur fuer
Rechnungen — keine sonstigen Mutationen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable, Optional

from ..util.http import http_json, http_bytes


def rechnung_zu_lexware(r, *, titel: str = "Rechnung") -> dict:
    """Mappt unsere ``Rechnung`` auf das lexoffice-Invoice-JSON (Kleinunternehmer)."""
    e = r.empfaenger
    adresse = {"name": e.anzeige, "countryCode": (e.land or "DE")}
    if e.strasse:
        adresse["street"] = e.strasse
    if e.plz:
        adresse["zip"] = e.plz
    if e.ort:
        adresse["city"] = e.ort

    line_items = []
    for p in r.positionen:
        line_items.append({
            "type": "custom",
            "name": p.bezeichnung,
            "quantity": float(p.menge),
            "unitName": p.einheit,
            "unitPrice": {
                "currency": "EUR",
                "netAmount": float(Decimal(str(p.einzelpreis))),
                "taxRatePercentage": 0,
            },
        })

    tax_type = "vatfree" if r.kleinunternehmer else "net"
    body = {
        "voucherDate": f"{r.datum.isoformat()}T00:00:00.000+01:00",
        "address": adresse,
        "lineItems": line_items,
        "totalPrice": {"currency": "EUR"},
        "taxConditions": {"taxType": tax_type},
        "shippingConditions": {
            "shippingDate": f"{(r.leistungsdatum or r.datum).isoformat()}T00:00:00.000+01:00",
            "shippingType": "delivery",
        },
        "title": titel,
    }
    if r.einleitung:
        body["introduction"] = r.einleitung
    bemerkungen = [t for t in (r.bemerkung,
                               (r.kleinunternehmer_hinweis if r.kleinunternehmer else ""),
                               (f"eBay-Bestellung: {r.bestell_referenz}"
                                if r.bestell_referenz else "")) if t]
    if bemerkungen:
        body["remark"] = "\n".join(bemerkungen)
    if r.kleinunternehmer:
        body["taxConditions"]["taxTypeNote"] = r.kleinunternehmer_hinweis
    return body


@dataclass
class LexwareInvoiceClient:
    api_key: str
    base_url: str = "https://api.lexware.io/v1"
    _poster: Callable[..., dict] = field(default=http_json, repr=False)
    _bytes: Callable[..., bytes] = field(default=http_bytes, repr=False)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json", "Content-Type": "application/json"}

    def rechnung_anlegen(self, r, *, finalize: bool = False,
                         titel: str = "Rechnung") -> dict:
        """Legt die Rechnung an. Gibt die lexoffice-Antwort ({id, ...}) zurueck."""
        body = rechnung_zu_lexware(r, titel=titel)
        url = f"{self.base_url.rstrip('/')}/invoices"
        if finalize:
            url += "?finalize=true"
        return self._poster(url, method="POST", payload=body, headers=self._headers())

    def pdf_laden(self, invoice_id: str) -> bytes:
        """Rendert/holt die Rechnungs-PDF (zweistufig: document -> file)."""
        base = self.base_url.rstrip("/")
        doc = self._poster(f"{base}/invoices/{invoice_id}/document",
                           headers=self._headers())
        file_id = doc.get("documentFileId")
        if not file_id:
            raise RuntimeError("Lexware lieferte keine documentFileId.")
        return self._bytes(f"{base}/files/{file_id}", headers=self._headers())
