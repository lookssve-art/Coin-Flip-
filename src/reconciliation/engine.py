"""Reconciliation: Bank <-> Belege.

Gleicht Bank-``Transaction``s gegen ``Receipt``s ab. Erkennt:
  * exakte Treffer (Betrag identisch, Datum nah),
  * Teilzahlungen (Bankbetrag < Belegbetrag),
  * Refunds/Chargebacks (Vorzeichenumkehr),
  * Betragsdifferenzen oberhalb der Toleranz -> ``REVIEW_REQUIRED``,
  * unzugeordnete Bankzeilen.

Grundsatz (Abschnitt 7): Beleg bestimmt die steuerliche Behandlung, die Bank das
*Ob/Wann* des Geldflusses. Bei EÜR ist das **Zahlungsdatum** der Bank das
Buchungsjahr. Widersprueche werden nie stillschweigend aufgeloest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional

from ..models import Receipt, Transaction


class MatchStatus(str, Enum):
    MATCHED = "matched"            # Betrag identisch (innerhalb Cent-Toleranz)
    PARTIAL = "partial"           # Teilzahlung
    REFUND = "refund"             # Rueckzahlung / Chargeback
    REVIEW_REQUIRED = "review_required"  # Differenz ueber Toleranz
    UNMATCHED = "unmatched"       # kein Beleg gefunden


@dataclass
class MatchResult:
    transaction_id: str
    status: MatchStatus
    receipt_id: Optional[str] = None
    differenz: Decimal = Decimal("0")   # Bankbetrag - Belegbetrag (Vorzeichen erhalten)
    buchungsjahr: Optional[int] = None  # EÜR: aus dem Zahlungsdatum der Bank
    gruende: list[str] = field(default_factory=list)


@dataclass
class Reconciler:
    betrags_toleranz: Decimal = Decimal("0.01")   # Cent-Rundung
    datum_toleranz_tage: int = 5
    teilzahlung_review: bool = True               # Teilzahlungen zusaetzlich markieren

    def _candidate_score(self, tx: Transaction, receipt: Receipt) -> Optional[tuple]:
        """Niedriger Score = besserer Treffer; None, wenn ausserhalb der Datumstoleranz."""
        tage = abs((tx.datum - receipt.datum).days)
        if tage > self.datum_toleranz_tage:
            return None
        betrags_diff = abs(abs(tx.betrag) - receipt.brutto)
        return (betrags_diff, tage)

    def match_one(self, tx: Transaction, receipts: list[Receipt]) -> MatchResult:
        buchungsjahr = tx.datum.year
        # Bereits explizit verknuepfter Beleg hat Vorrang.
        kandidaten = receipts
        if tx.receipt_id:
            kandidaten = [r for r in receipts if r.id == tx.receipt_id] or receipts

        bewertet = []
        for r in kandidaten:
            score = self._candidate_score(tx, r)
            if score is not None:
                bewertet.append((score, r))
        if not bewertet:
            return MatchResult(tx.id, MatchStatus.UNMATCHED, buchungsjahr=buchungsjahr,
                               gruende=["Kein Beleg innerhalb der Datums-/Betragstoleranz"])

        bewertet.sort(key=lambda x: x[0])
        receipt = bewertet[0][1]
        differenz = abs(tx.betrag) - receipt.brutto  # >0: Bank hoeher, <0: Bank niedriger

        # Refund / Chargeback: Beleg ist Einnahme (Verkauf), Bank ist Abfluss (oder umgekehrt).
        if (tx.betrag < 0) and receipt.kategorie.lower() in ("verkauf", "umsatz", "erloes"):
            return MatchResult(tx.id, MatchStatus.REFUND, receipt.id, differenz,
                               buchungsjahr, ["Vorzeichenumkehr: Refund/Chargeback"])

        if abs(differenz) <= self.betrags_toleranz:
            return MatchResult(tx.id, MatchStatus.MATCHED, receipt.id, Decimal("0"),
                               buchungsjahr)

        if differenz < 0:
            # Bank niedriger als Beleg -> Teilzahlung.
            gruende = ["Teilzahlung (Bankbetrag < Belegbetrag)"]
            status = MatchStatus.PARTIAL
            if self.teilzahlung_review:
                gruende.append("Beleg <-> Bank Betragsdifferenz")
                status = MatchStatus.REVIEW_REQUIRED
            return MatchResult(tx.id, status, receipt.id, differenz, buchungsjahr, gruende)

        # Bank hoeher als Beleg -> ueber Toleranz -> Review.
        return MatchResult(tx.id, MatchStatus.REVIEW_REQUIRED, receipt.id, differenz,
                           buchungsjahr, ["Beleg <-> Bank Betragsdifferenz (Bank hoeher)"])

    def reconcile(self, transactions: list[Transaction],
                  receipts: list[Receipt]) -> list[MatchResult]:
        """Gleicht alle Transaktionen ab. Ein Beleg wird hoechstens einmal verbraucht."""
        verbleibend = list(receipts)
        ergebnisse: list[MatchResult] = []
        for tx in transactions:
            res = self.match_one(tx, verbleibend)
            if res.receipt_id is not None:
                verbleibend = [r for r in verbleibend if r.id != res.receipt_id]
            ergebnisse.append(res)
        return ergebnisse
