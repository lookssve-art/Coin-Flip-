"""DATEV-/CSV-Export (offline).

Erzeugt prueffaehige CSV-Journale als Entwurf — fuer den Steuerberater (DATEV) oder
zur Eigenkontrolle. Kein Live-API-Zugriff; rein lokale Dateierzeugung.

Zwei Journale:
  * Buchungsjournal     — Reconciliation-Ergebnisse (Bank <-> Beleg).
  * Differenz-Journal    — § 25a-Margen je Artikel/Posten (Pflicht-Aufzeichnung).
"""

from __future__ import annotations

import csv
from typing import Iterable

from ..reconciliation import MatchResult
from ..tax.differenzbesteuerung import MargenErgebnis


def schreibe_buchungsjournal(pfad: str, ergebnisse: Iterable[MatchResult]) -> int:
    """Schreibt Reconciliation-Ergebnisse als CSV. Rueckgabe: Anzahl Zeilen."""
    felder = ["transaction_id", "status", "receipt_id", "differenz", "buchungsjahr", "gruende"]
    n = 0
    with open(pfad, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=felder, delimiter=";")
        writer.writeheader()
        for r in ergebnisse:
            writer.writerow({
                "transaction_id": r.transaction_id,
                "status": r.status.value,
                "receipt_id": r.receipt_id or "",
                "differenz": f"{r.differenz}",
                "buchungsjahr": r.buchungsjahr or "",
                "gruende": " | ".join(r.gruende),
            })
            n += 1
    return n


def schreibe_differenz_journal(pfad: str, posten: Iterable[tuple[str, MargenErgebnis]]) -> int:
    """Schreibt das § 25a-Differenzbesteuerungs-Journal.

    ``posten`` ist eine Folge von (artikel_id, MargenErgebnis). Die offene USt darf
    nicht ausgewiesen werden — das Journal dient der internen Bemessungsgrundlage.
    """
    felder = ["artikel_id", "verkauf", "einkauf", "marge_brutto", "netto_marge",
              "ust_satz", "ust_betrag", "hinweis"]
    n = 0
    with open(pfad, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=felder, delimiter=";")
        writer.writeheader()
        for artikel_id, m in posten:
            writer.writerow({
                "artikel_id": artikel_id,
                "verkauf": f"{m.verkauf}",
                "einkauf": f"{m.einkauf}",
                "marge_brutto": f"{m.marge}",
                "netto_marge": f"{m.netto_marge}",
                "ust_satz": f"{m.ust_satz}",
                "ust_betrag": f"{m.ust_betrag}",
                "hinweis": m.hinweis,
            })
            n += 1
    return n
