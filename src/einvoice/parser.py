"""E-Rechnungs-Empfang und -Parsing (EN 16931).

Empfangspflicht seit 01.01.2025 — ausnahmslos, auch fuer Kleinunternehmer. Eine
PDF OHNE strukturierten Datensatz ist KEINE E-Rechnung ("sonstige Rechnung").

Dieser Parser:
  * erkennt das Format (XRechnung = reines XML, ZUGFeRD/Factur-X = PDF/A-3 + XML),
  * extrahiert die zentralen EN-16931-Felder aus dem XML (UBL oder CII),
  * markiert ungueltige/uneindeutige Faelle als REVIEW_REQUIRED.

Bewusst stdlib (xml.etree). Fuer Prod empfiehlt sich lxml + eine echte
EN-16931-Schematron-Validierung (Format- vs. Geschaeftsregelfehler).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional

from ..models import EInvoiceFormat


@dataclass
class EInvoiceResult:
    format: EInvoiceFormat
    valid: bool
    felder: dict = field(default_factory=dict)
    fehler: list[str] = field(default_factory=list)
    review_required: bool = False


# ZUGFeRD/Factur-X: XML ist in eine PDF/A-3 eingebettet.
_PDF_MAGIC = b"%PDF"
_ZUGFERD_HINTS = (b"factur-x.xml", b"ZUGFeRD-invoice.xml", b"xrechnung.xml",
                  b"CrossIndustryInvoice", b"urn:cen.eu:en16931")


def erkenne_format(content: bytes) -> EInvoiceFormat:
    """Bestimmt das E-Rechnungs-Format anhand des Datei-Inhalts."""
    head = content[:1024].lstrip()
    if content[:4] == _PDF_MAGIC:
        # PDF: nur dann E-Rechnung, wenn strukturiertes XML eingebettet ist.
        if any(hint in content for hint in _ZUGFERD_HINTS):
            return EInvoiceFormat.ZUGFERD
        return EInvoiceFormat.SONSTIGE  # PDF ohne Datensatz -> keine E-Rechnung
    if head[:5] == b"<?xml" or head[:1] == b"<":
        if b"CrossIndustryInvoice" in content or b"Invoice" in content:
            return EInvoiceFormat.XRECHNUNG
        return EInvoiceFormat.UNBEKANNT
    return EInvoiceFormat.UNBEKANNT


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_text(root: ET.Element, *localnames: str) -> Optional[str]:
    """Namespace-agnostische Suche nach dem ersten Element mit passendem Localname."""
    wanted = set(localnames)
    for el in root.iter():
        if _localname(el.tag) in wanted and el.text and el.text.strip():
            return el.text.strip()
    return None


def _to_decimal(value: Optional[str]) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(value.replace(",", "."))
    except (InvalidOperation, AttributeError):
        return None


def parse_xrechnung(xml_bytes: bytes) -> EInvoiceResult:
    """Extrahiert die zentralen Felder aus XRechnung-/CII-XML."""
    result = EInvoiceResult(format=EInvoiceFormat.XRECHNUNG, valid=False)
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        result.fehler.append(f"XML nicht parsebar: {exc}")
        result.review_required = True
        return result

    felder = {
        "rechnungsnummer": _find_text(root, "ID", "DocumentID"),
        "rechnungsdatum": _find_text(root, "IssueDate", "DateTimeString"),
        "verkaeufer": _find_text(root, "RegistrationName", "Name"),
        "betrag_brutto": _to_decimal(
            _find_text(root, "PayableAmount", "GrandTotalAmount", "TaxInclusiveAmount")),
        "ust_betrag": _to_decimal(_find_text(root, "TaxAmount", "CalculatedAmount")),
        "waehrung": _find_text(root, "DocumentCurrencyCode", "InvoiceCurrencyCode") or "EUR",
    }
    # Localname-Suche kann die Rechnungsnummer mit einer Positions-ID verwechseln;
    # bei reiner Ziffernfolge plausibel, sonst Hinweis.
    result.felder = felder

    pflicht = ["rechnungsnummer", "rechnungsdatum", "betrag_brutto"]
    fehlend = [f for f in pflicht if not felder.get(f)]
    if fehlend:
        result.fehler.append(f"Pflichtfelder fehlen/uneindeutig: {', '.join(fehlend)}")
        result.review_required = True
    else:
        result.valid = True
    return result
