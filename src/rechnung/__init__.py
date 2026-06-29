"""Rechnungsmodul — erzeugt rechtskonforme (Kleinunternehmer-)Rechnungen aus
eBay-Verkaeufen, vergibt fortlaufende Nummern (§14 UStG), rendert sie und haelt
ein idempotentes Register. Die Lexware-Uebertragung liegt in
``src.integrations.lexware_invoices``.

Bewusst quellenagnostisch und ohne Fremdpakete: das Modell nimmt einen
``PlatformSale`` + Absenderdaten und liefert eine ``Rechnung``; Rendering als
HTML/Text. Der PDF-/Buchungs-Render kann optional Lexware uebernehmen.
"""

from .modell import Rechnung, Position, Absender, Empfaenger
from .nummer import Nummernkreis
from .generator import rechnung_aus_verkauf, render_html, render_text
from .register import RechnungsRegister

__all__ = [
    "Rechnung", "Position", "Absender", "Empfaenger",
    "Nummernkreis", "rechnung_aus_verkauf", "render_html", "render_text",
    "RechnungsRegister",
]
