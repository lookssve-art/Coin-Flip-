"""Payout-Reconciliation: eBay-Auszahlungen <-> Bank-Eingaenge.

eBay zahlt gesammelt aus (eine Bank-Gutschrift = viele Einzelumsaetze). Diese Stufe
gleicht die eBay-PAYOUT-Betraege gegen die Bank-Eingaenge ab — getrennt von der
Beleg-Reconciliation (Abschnitt 3/5.1 der Spezifikation: Auszahlungen != Einzelumsatz).
Differenzen ueber Toleranz werden markiert (REVIEW_REQUIRED), nie stillschweigend
aufgeloest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from ..models import Transaction
from ..util.datum import parse_iso


class PayoutStatus(str, Enum):
    MATCHED = "matched"
    DIFFERENZ = "differenz"          # Betrag weicht ueber Toleranz ab -> Review
    UNMATCHED = "unmatched"          # kein Bank-Eingang gefunden


@dataclass
class Payout:
    id: str
    datum: Optional[date]
    betrag: Decimal


@dataclass
class PayoutMatch:
    payout_id: str
    status: PayoutStatus
    bank_tx_id: Optional[str] = None
    payout_betrag: Decimal = Decimal("0")
    bank_betrag: Decimal = Decimal("0")
    differenz: Decimal = Decimal("0")
    gruende: list = field(default_factory=list)


def extrahiere_payouts(raw_transactions: list[dict]) -> list[Payout]:
    """Filtert PAYOUT-Transaktionen aus rohen eBay-Finances-Daten."""
    payouts: list[Payout] = []
    for t in raw_transactions:
        if (t.get("transactionType") or "").upper() != "PAYOUT":
            continue
        amount = t.get("amount") or {}
        betrag = Decimal(str(amount.get("value", "0"))) if isinstance(amount, dict) else Decimal("0")
        payouts.append(Payout(
            id=t.get("payoutId") or t.get("transactionId") or "",
            datum=parse_iso(t.get("payoutDate") or t.get("transactionDate")),
            betrag=betrag,
        ))
    return payouts


@dataclass
class PayoutReconciler:
    betrags_toleranz: Decimal = Decimal("0.01")
    datum_toleranz_tage: int = 5

    def reconcile(self, payouts: list[Payout],
                  bank_txs: list[Transaction]) -> list[PayoutMatch]:
        """Gleicht Payouts gegen Bank-Eingaenge (positive Betraege) ab."""
        # Nur Eingaenge kommen als Auszahlung in Frage.
        verbleibend = [t for t in bank_txs if t.betrag > 0]
        ergebnisse: list[PayoutMatch] = []
        for p in payouts:
            kandidat = self._beste_bank(p, verbleibend)
            if kandidat is None:
                ergebnisse.append(PayoutMatch(
                    p.id, PayoutStatus.UNMATCHED, payout_betrag=p.betrag,
                    gruende=["Kein Bank-Eingang in Toleranz"]))
                continue
            verbleibend = [t for t in verbleibend if t.id != kandidat.id]
            differenz = kandidat.betrag - p.betrag
            if abs(differenz) <= self.betrags_toleranz:
                ergebnisse.append(PayoutMatch(
                    p.id, PayoutStatus.MATCHED, kandidat.id, p.betrag, kandidat.betrag,
                    Decimal("0")))
            else:
                ergebnisse.append(PayoutMatch(
                    p.id, PayoutStatus.DIFFERENZ, kandidat.id, p.betrag, kandidat.betrag,
                    differenz, ["Payout <-> Bank Betragsdifferenz"]))
        return ergebnisse

    def _beste_bank(self, p: Payout, kandidaten: list[Transaction]) -> Optional[Transaction]:
        bewertet = []
        for t in kandidaten:
            if p.datum is not None and abs((t.datum - p.datum).days) > self.datum_toleranz_tage:
                continue
            betrags_diff = abs(t.betrag - p.betrag)
            tage = abs((t.datum - p.datum).days) if p.datum else 99
            bewertet.append(((betrags_diff, tage), t))
        if not bewertet:
            return None
        bewertet.sort(key=lambda x: x[0])
        return bewertet[0][1]
