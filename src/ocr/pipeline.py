"""Beleg-Pipeline: Eingang -> Erkennung -> Extraktion -> Klassifikation -> Ablage.

Orchestriert die Beleg-Verarbeitung GoBD-konform:
  1. Format erkennen: E-Rechnung (strukturierter Datensatz) vs. Bild/PDF (OCR).
  2. Felder gewinnen: E-Rechnung -> Parser; sonst OCR-Text -> Heuristik.
  3. Klassifizieren: Kategorie + Vorsteuer-Entscheidung.
  4. Original revisionssicher ablegen (WORM) -> archived_hash.
  5. Receipt erzeugen; unsichere Faelle in die Review-Queue (kein Raten).

Der OCR-Anbieter ist injizierbar (callable ``(content, mime) -> OcrErgebnis``),
damit Cloud-OCR (Textract/Document AI) ohne Code-Aenderung vorgeschaltet werden
kann und die Pipeline offline testbar bleibt.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Callable, Optional

from ..einvoice import erkenne_format, parse_xrechnung
from ..models import EInvoiceFormat, Receipt
from ..review import ReviewQueue
from ..storage import ReceiptStore
from .classify import Klassifikation, RuleBasedClassifier
from .extract import extrahiere_felder

# Schwelle, unterhalb derer ein Beleg zwingend in die Review-Queue geht.
CONFIDENCE_REVIEW_SCHWELLE = 0.7


@dataclass
class OcrErgebnis:
    text: str
    confidence: float = 0.0


# Default-OCR: liefert nichts (Cloud-OCR ist vorzuschalten) -> erzwingt Review.
def _kein_ocr(content: bytes, mime: str) -> OcrErgebnis:
    return OcrErgebnis(text="", confidence=0.0)


@dataclass
class BelegPipeline:
    store: ReceiptStore
    review_queue: ReviewQueue
    classifier: object = None                      # hat .classify(text, haendler)
    ocr: Callable[[bytes, str], OcrErgebnis] = _kein_ocr
    _counter: object = None

    def __post_init__(self):
        if self.classifier is None:
            self.classifier = RuleBasedClassifier()
        self._counter = itertools.count(1)

    def _neue_id(self) -> str:
        return f"BELEG-{next(self._counter):05d}"

    def verarbeite(self, content: bytes, *, mime: str = "application/pdf",
                   suffix: str = "") -> Receipt:
        """Verarbeitet einen Beleg und gibt das erzeugte ``Receipt`` zurueck."""
        beleg_id = self._neue_id()
        review_gruende: list[str] = []

        fmt = erkenne_format(content)
        if fmt in (EInvoiceFormat.XRECHNUNG, EInvoiceFormat.ZUGFERD):
            receipt = self._aus_erechnung(beleg_id, content, fmt, review_gruende)
        else:
            receipt = self._aus_ocr(beleg_id, content, mime, review_gruende)

        # Original revisionssicher ablegen (8 J. Aufbewahrung).
        abgelegt = self.store.store(content, suffix or _suffix_fuer(fmt, mime))
        receipt.archived_hash = abgelegt.sha256

        # Unsichere Faelle -> Review-Queue (keine stille Verbuchung).
        if (receipt.ocr_confidence or 0) < CONFIDENCE_REVIEW_SCHWELLE:
            review_gruende.append("Niedrige Extraktions-/OCR-Confidence")
        if receipt.vorsteuer_abzug == "unsicher":
            review_gruende.append("Vorsteuerabzug unklar")
        for grund in review_gruende:
            self.review_queue.add(grund, bezug=beleg_id)

        return receipt

    # ------------------------------------------------------------------ #
    def _aus_erechnung(self, beleg_id: str, content: bytes, fmt: EInvoiceFormat,
                       review_gruende: list[str]) -> Receipt:
        res = parse_xrechnung(content) if fmt == EInvoiceFormat.XRECHNUNG else None
        # ZUGFeRD: eingebettetes XML extrahieren waere der Produktionsschritt;
        # im MVP wird der Fall markiert statt geraten.
        if res is None or not res.valid:
            if fmt == EInvoiceFormat.ZUGFERD:
                review_gruende.append("ZUGFeRD: eingebettetes XML noch nicht extrahiert")
            else:
                review_gruende.append("E-Rechnung mit Format-/Geschaeftsregelfehler")
            felder = (res.felder if res else {})
            brutto = felder.get("betrag_brutto") or Decimal("0")
            ust = felder.get("ust_betrag") or Decimal("0")
            haendler = felder.get("verkaeufer") or "unbekannt"
            confidence = 0.0
        else:
            brutto = res.felder["betrag_brutto"]
            ust = res.felder.get("ust_betrag") or Decimal("0")
            haendler = res.felder.get("verkaeufer") or "unbekannt"
            confidence = 1.0  # strukturierter Datensatz -> kein OCR-Risiko

        klass = self.classifier.classify(haendler, haendler=haendler)
        netto = (brutto - ust) if brutto else Decimal("0")
        ust_satz = _satz_aus_betraegen(netto, ust)
        return Receipt(
            id=beleg_id, datum=date.today(), haendler=haendler,
            brutto=Decimal(brutto), netto=netto, ust_satz=ust_satz, ust_betrag=Decimal(ust),
            kategorie=klass.kategorie, vorsteuer_abzug=klass.vorsteuer_abzug,
            ocr_confidence=confidence,
        )

    def _aus_ocr(self, beleg_id: str, content: bytes, mime: str,
                 review_gruende: list[str]) -> Receipt:
        ocr = self.ocr(content, mime)
        felder = extrahiere_felder(ocr.text)
        klass = self.classifier.classify(ocr.text, haendler=felder.haendler)
        if felder.fehlend:
            review_gruende.append(f"Felder fehlen: {', '.join(felder.fehlend)}")
        # Gesamt-Confidence = Min aus OCR-Lesequalitaet und Feld-Vollstaendigkeit.
        confidence = round(min(ocr.confidence, felder.confidence), 2)
        return Receipt(
            id=beleg_id, datum=felder.datum or date.today(),
            haendler=felder.haendler or "unbekannt",
            brutto=felder.brutto or Decimal("0"), netto=felder.netto or Decimal("0"),
            ust_satz=felder.ust_satz or Decimal("0"),
            ust_betrag=felder.ust_betrag or Decimal("0"),
            kategorie=klass.kategorie, vorsteuer_abzug=klass.vorsteuer_abzug,
            ocr_confidence=confidence,
        )


def _suffix_fuer(fmt: EInvoiceFormat, mime: str) -> str:
    if fmt == EInvoiceFormat.XRECHNUNG:
        return ".xml"
    if fmt == EInvoiceFormat.ZUGFERD:
        return ".pdf"
    if "pdf" in mime:
        return ".pdf"
    if "png" in mime:
        return ".png"
    if "jpeg" in mime or "jpg" in mime:
        return ".jpg"
    return ""


def _satz_aus_betraegen(netto: Decimal, ust: Decimal) -> Decimal:
    if netto and ust:
        satz = (ust / netto * Decimal("100")).quantize(Decimal("1"))
        if satz in (Decimal("7"), Decimal("19")):
            return satz
    return Decimal("0")
