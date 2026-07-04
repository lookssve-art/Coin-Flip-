"""Warenbuch / Bestandsübersicht (freiwillig, für den Überblick + §25a-Vorsorge).

Führt Käufe (eBay + in Lexware hinterlegte Einkaufsbelege) und Verkäufe zusammen,
zeigt Bestand (gekauft − verkauft) und Marge je Artikelgruppe. NICHT fürs
Finanzamt nötig (KU/EÜR braucht keine Artikel-Zuordnung), aber sauberer Überblick
und Absicherung, falls je §25a nötig wird. Persistenter Speicher = Selbst-Lernen.
"""

from .buch import (Warenbuch, erstelle_warenbuch, render_bestand_text,
                   schreibe_warenbuch_json)

__all__ = ["Warenbuch", "erstelle_warenbuch", "render_bestand_text",
           "schreibe_warenbuch_json"]
