"""Plausibilitaets- und Dublettenpruefung (Master-Prompt Punkt 4 + 11).

Formale Pruefungen ohne Netzwerk: IBAN-Pruefsumme (ISO 7064 mod-97), USt-IdNr-
Format je Land, Rechnungs-Arithmetik (netto + USt = brutto), Pflichtfelder,
Datums-/Faelligkeitslogik sowie Dublettenerkennung. Liefert strukturierte Befunde
(``Befund``) statt zu raten — Fehler werden dokumentiert, nicht stillschweigend
korrigiert.
"""

from .checks import (pruefe_iban, pruefe_ust_id, pruefe_rechnung_arithmetik,
                     pruefe_pflichtfelder, ist_dublette, dubletten_schluessel,
                     Befund, Schwere)

__all__ = ["pruefe_iban", "pruefe_ust_id", "pruefe_rechnung_arithmetik",
           "pruefe_pflichtfelder", "ist_dublette", "dubletten_schluessel",
           "Befund", "Schwere"]
