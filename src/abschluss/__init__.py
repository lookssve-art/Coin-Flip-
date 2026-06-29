"""Monatsabschluss / BWA (Master-Prompt Punkt 13).

Verdichtet die EÜR-Auswertung + Verkaeufe zu einer betriebswirtschaftlichen
Auswertung: Umsatz, Wareneinkauf, Rohertrag, Kostenblöcke (mit SKR-Konto),
Gewinn, Kennzahlen (Rohertrags-/Kostenquote, Marge) und Monatsverlauf.
Rein rechnerisch, ohne Netzwerk.
"""

from .bwa import erstelle_bwa, render_bwa_text, schreibe_bwa_csv, BWA

__all__ = ["erstelle_bwa", "render_bwa_text", "schreibe_bwa_csv", "BWA"]
