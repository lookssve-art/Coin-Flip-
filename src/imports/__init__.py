"""Read-only Import-Adapter (Bank, eBay) — normalisieren externe Rohdaten.

Bewusst quellenagnostisch: die Adapter nehmen bereits geparste Zeilen (dicts) und
erzeugen die internen Datenmodelle. Der eigentliche API-/CSV-Abruf (Qonto/Finom,
eBay Finances) wird in spaeteren Stufen davorgeschaltet — die Normalisierungs- und
Reconciliation-Logik bleibt dadurch ohne Live-Credentials testbar.
"""

from .bank import importiere_bank_transaktionen, idempotency_key
from .ebay import importiere_ebay_verkaeufe
from .lexware_bank import importiere_lexware_bank, lese_lexware_bank_csv
from .ausgaben_csv import lese_ausgaben_csv

__all__ = [
    "importiere_bank_transaktionen",
    "idempotency_key",
    "importiere_ebay_verkaeufe",
    "importiere_lexware_bank",
    "lese_lexware_bank_csv",
    "lese_ausgaben_csv",
]
