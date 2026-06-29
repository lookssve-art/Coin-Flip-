"""Datenmodell (Abschnitt 6 der Spezifikation).

Bewusst als stdlib-dataclasses gehalten: das Compliance-Fundament soll ohne
ORM/Framework pruefbar und portierbar sein. Geldbetraege werden als
``decimal.Decimal`` gefuehrt — niemals float (Rundungsfehler in der USt).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class TaxScheme(str, Enum):
    """Besteuerungsart pro Artikel/Vorgang."""

    REGEL = "regel"            # Regelbesteuerung 0/7/19 %
    DIFFERENZ = "differenz"    # Differenzbesteuerung § 25a UStG (Marge)


class ReviewStatus(str, Enum):
    OPEN = "open"
    REVIEW_REQUIRED = "review_required"   # menschliche Freigabe noetig
    APPROVED = "approved"
    REJECTED = "rejected"


class Source(str, Enum):
    EBAY = "ebay"
    WEBSHOP = "webshop"
    BANK = "bank"
    MANUELL = "manuell"


class EInvoiceFormat(str, Enum):
    XRECHNUNG = "xrechnung"        # reines XML (EN 16931)
    ZUGFERD = "zugferd"           # PDF/A-3 + eingebettetes XML (Factur-X)
    SONSTIGE = "sonstige"         # PDF ohne strukturierten Datensatz -> keine E-Rechnung
    UNBEKANNT = "unbekannt"


# Zulaessige USt-Saetze in Lexware Office (Abschnitt 3).
ERLAUBTE_UST_SAETZE = (Decimal("0"), Decimal("5"), Decimal("7"), Decimal("16"), Decimal("19"))


# --------------------------------------------------------------------------- #
# Stammdaten
# --------------------------------------------------------------------------- #
@dataclass
class Customer:
    id: str
    name: str
    country: str = "DE"               # ISO-2
    vat_id: Optional[str] = None      # USt-IdNr (Reverse-Charge-Pruefung)
    is_business: bool = False         # B2B vs. B2C (E-Rechnung/OSS-Relevanz)


@dataclass
class Product:
    id: str
    bezeichnung: str
    tax_scheme: TaxScheme = TaxScheme.REGEL
    ust_satz: Decimal = Decimal("19")           # nur bei REGEL relevant
    purchase_price: Optional[Decimal] = None    # Einkaufspreis (Pflicht bei DIFFERENZ)
    purchase_receipt_ref: Optional[str] = None  # Verknuepfung zum Einkaufsbeleg


# --------------------------------------------------------------------------- #
# Belege / Rechnungen
# --------------------------------------------------------------------------- #
@dataclass
class Receipt:
    """Eingangs-/Ausgangsbeleg (OCR oder E-Rechnung)."""

    id: str
    datum: date
    haendler: str
    brutto: Decimal
    netto: Decimal
    ust_satz: Decimal
    ust_betrag: Decimal
    kategorie: str = "unklassifiziert"
    vorsteuer_abzug: str = "unsicher"   # ja | nein | unsicher
    zahlungsart: str = "unbekannt"
    ocr_confidence: Optional[float] = None
    archived_hash: Optional[str] = None  # Hash des revisionssicher abgelegten Originals


@dataclass
class Invoice:
    id: str
    datum: date
    customer_id: str
    betrag_brutto: Decimal
    e_invoice_format: EInvoiceFormat = EInvoiceFormat.UNBEKANNT
    structured_payload: Optional[dict] = None  # ausgelesene EN-16931-Felder
    archived_hash: Optional[str] = None


# --------------------------------------------------------------------------- #
# Transaktionen / Plattform
# --------------------------------------------------------------------------- #
@dataclass
class Transaction:
    id: str
    datum: date                       # Zahlungsdatum -> bei EUER das Buchungsjahr
    betrag: Decimal                   # +Einnahme / -Ausgabe
    source: Source = Source.BANK
    beschreibung: str = ""
    receipt_id: Optional[str] = None  # gematchter Beleg
    idempotency_key: Optional[str] = None  # gegen Doppelbuchungen


@dataclass
class PlatformSale:
    id: str
    datum: date
    plattform: Source
    brutto: Decimal
    gebuehren: Decimal = Decimal("0")
    versand: Decimal = Decimal("0")
    refund: Decimal = Decimal("0")
    product_id: Optional[str] = None
    product_name: str = ""                       # Artikeltitel (fuer Rechnungs-Bezeichnung)
    menge: Decimal = Decimal("1")                # verkaufte Stueckzahl (eBay QuantityPurchased)
    einzelpreis: Decimal = Decimal("0")          # Einzelpreis (eBay TransactionPrice); 0 = aus brutto/menge
    customer_country: str = "DE"
    customer_name: str = ""                      # Rechnungsadresse (soweit von eBay geliefert)
    customer_street: str = ""
    customer_zip: str = ""
    customer_city: str = ""
    customer_is_business: bool = False          # B2B (Reverse-Charge) vs. B2C (OSS)
    tax_scheme: TaxScheme = TaxScheme.REGEL
    ebay_collected_vat: Decimal = Decimal("0")  # Deemed-Supplier: von eBay abgefuehrt


# --------------------------------------------------------------------------- #
# Nachvollziehbarkeit / GoBD
# --------------------------------------------------------------------------- #
@dataclass
class Decision:
    """Protokolliert jede automatische Entscheidung (GoBD-Nachvollziehbarkeit)."""

    grund: str
    regel: str
    quellen: list[str] = field(default_factory=list)
    unsicherheitsgrad: float = 0.0
    zeitstempel: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


@dataclass
class ReviewItem:
    id: str
    grund: str
    bezug: str                         # ID des betroffenen Objekts
    status: ReviewStatus = ReviewStatus.REVIEW_REQUIRED
    erstellt: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    aufgeloest_von: Optional[str] = None


@dataclass
class ProcedureDoc:
    """Versionierte Verfahrensdokumentation (GoBD)."""

    version: str
    erstellt: str
    inhalt_md: str


def to_jsonable(obj) -> dict:
    """Dataclass -> JSON-serialisierbares dict (Decimal/Enum/date als str)."""

    def convert(value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, dict):
            return {k: convert(v) for k, v in value.items()}
        if isinstance(value, list):
            return [convert(v) for v in value]
        return value

    return {k: convert(v) for k, v in asdict(obj).items()}
