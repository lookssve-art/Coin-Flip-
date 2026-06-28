"""Belegklassifikation: regelbasiert (offline) und Claude-gestuetzt.

Beide liefern eine ``Klassifikation`` (Kategorie + Vorsteuer-Entscheidung +
Confidence). Die Pipeline nutzt standardmaessig den regelbasierten Klassifikator
(deterministisch, ohne Netzwerk, testbar); der Claude-Klassifikator ist ein
optionales Upgrade fuer schwierige/unklare Belege.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

# Kategorien analog Abschnitt 5.2 der Spezifikation.
KATEGORIEN = ("wareneinkauf", "buero", "software", "versand", "werbung",
              "gebuehren", "reise", "sonstiges")

_SCHLUESSELWOERTER = {
    "wareneinkauf": ("ankauf", "einkauf", "ware", "karten", "booster", "display",
                     "pokemon", "tcg", "sammel"),
    "buero": ("buero", "papier", "drucker", "toner", "ordner"),
    "software": ("software", "lizenz", "saas", "abo", "cloud", "adobe", "microsoft"),
    "versand": ("versand", "porto", "dhl", "hermes", "dpd", "paket", "frachtkosten"),
    "werbung": ("werbung", "ads", "anzeige", "marketing", "promoted"),
    "gebuehren": ("gebuehr", "fee", "provision", "paypal", "stripe", "ebay-gebuehr"),
    "reise": ("hotel", "bahn", "flug", "taxi", "reise", "uebernachtung"),
}


@dataclass
class Klassifikation:
    kategorie: str = "sonstiges"
    vorsteuer_abzug: str = "unsicher"   # ja | nein | unsicher
    confidence: float = 0.0
    quelle: str = "regel"               # regel | claude
    begruendung: str = ""


# --------------------------------------------------------------------------- #
class RuleBasedClassifier:
    """Deterministische Schluesselwort-Klassifikation."""

    def classify(self, text: str, haendler: str | None = None) -> Klassifikation:
        haystack = f"{text or ''} {haendler or ''}".lower()
        treffer: dict[str, int] = {}
        for kat, woerter in _SCHLUESSELWOERTER.items():
            n = sum(1 for w in woerter if w in haystack)
            if n:
                treffer[kat] = n
        if not treffer:
            return Klassifikation(kategorie="sonstiges", vorsteuer_abzug="unsicher",
                                  confidence=0.2, quelle="regel",
                                  begruendung="Keine Schluesselwoerter erkannt")
        kategorie = max(treffer, key=treffer.get)
        # Vorsteuer: bei klaren Betriebsausgaben ja; private/gemischte Faelle bleiben unsicher.
        vorsteuer = "ja" if kategorie in (
            "wareneinkauf", "buero", "software", "versand", "werbung", "gebuehren") else "unsicher"
        confidence = min(0.5 + 0.15 * treffer[kategorie], 0.9)
        return Klassifikation(kategorie=kategorie, vorsteuer_abzug=vorsteuer,
                              confidence=round(confidence, 2), quelle="regel",
                              begruendung=f"{treffer[kategorie]} Schluesselwort-Treffer")


# --------------------------------------------------------------------------- #
# Strukturiertes Ausgabeschema fuer den Claude-Klassifikator (EN 16931-agnostisch).
_SCHEMA = {
    "type": "object",
    "properties": {
        "kategorie": {"type": "string", "enum": list(KATEGORIEN)},
        "vorsteuer_abzug": {"type": "string", "enum": ["ja", "nein", "unsicher"]},
        "confidence": {"type": "number"},
        "begruendung": {"type": "string"},
    },
    "required": ["kategorie", "vorsteuer_abzug", "confidence", "begruendung"],
    "additionalProperties": False,
}

_SYSTEM = (
    "Du bist ein deutscher Buchhaltungs-Assistent. Klassifiziere einen Beleg in "
    "genau eine Kategorie und entscheide ueber den Vorsteuerabzug. Erfinde nichts: "
    "bei Unsicherheit setze vorsteuer_abzug='unsicher' und eine niedrige confidence. "
    "Antworte ausschliesslich im vorgegebenen JSON-Schema."
)


class ClaudeClassifier:
    """Claude-gestuetzte Klassifikation via offizielles Anthropic-SDK.

    Das SDK wird erst beim Aufruf importiert, damit die Pipeline ohne die
    Abhaengigkeit ``anthropic`` lauffaehig und testbar bleibt. Modell: Opus 4.8.
    """

    def __init__(self, api_key: str, model: str = "claude-opus-4-8"):
        self.api_key = api_key
        self.model = model
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            import anthropic  # lazy: nur noetig, wenn Claude tatsaechlich genutzt wird
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def classify(self, text: str, haendler: str | None = None) -> Klassifikation:
        client = self._ensure_client()
        inhalt = f"Haendler: {haendler or 'unbekannt'}\n\nBelegtext:\n{text or ''}"
        # Klassifikation ist eine einfache Aufgabe -> effort 'low'; strukturierte
        # Ausgabe per output_config.format (kein Prefill, kein Thinking noetig).
        response = client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=_SYSTEM,
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": _SCHEMA},
            },
            messages=[{"role": "user", "content": inhalt}],
        )
        roh = next((b.text for b in response.content if b.type == "text"), "{}")
        data = json.loads(roh)
        return Klassifikation(
            kategorie=data["kategorie"],
            vorsteuer_abzug=data["vorsteuer_abzug"],
            confidence=float(data["confidence"]),
            quelle="claude",
            begruendung=data.get("begruendung", ""),
        )
