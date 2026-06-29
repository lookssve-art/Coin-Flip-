"""Automatische Kontierung: interne Kategorie -> SKR03/SKR04-Konto + USt-Schluessel.

Bildet jede Buchungskategorie auf ein Sachkonto ab (Standardkontenrahmen SKR03
*oder* SKR04) inklusive Umsatzsteuer-Behandlung. Die Default-Tabelle ist ein
fachlich ueblicher VORSCHLAG — Kontonummern variieren je Mandant/Berater und sind
in config.yaml (``kontierung.skr03`` / ``kontierung.skr04``) frei ueberschreibbar.
Unsichere Faelle werden nie geraten, sondern als ``konto=""`` zurueckgegeben
(-> Review).
"""

from .konten import (kontiere, konto_fuer, SKR03, SKR04, UST_SCHLUESSEL,
                     Buchungssatz)

__all__ = ["kontiere", "konto_fuer", "SKR03", "SKR04", "UST_SCHLUESSEL",
           "Buchungssatz"]
