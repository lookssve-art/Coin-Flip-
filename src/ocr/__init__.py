"""Beleg-/OCR-Verarbeitung (MVP-Punkt 3).

PDF/Bild -> OCR -> Klassifikation -> Vorsteuer-Entscheidung -> strukturierte
Speicherung; bei E-Rechnung wird der strukturierte Datensatz geparst statt OCR.
Unsichere Faelle gehen in die Review-Queue.
"""

from .extract import extrahiere_felder, ExtraktionsErgebnis
from .classify import RuleBasedClassifier, ClaudeClassifier, Klassifikation
from .pipeline import BelegPipeline

__all__ = [
    "extrahiere_felder",
    "ExtraktionsErgebnis",
    "RuleBasedClassifier",
    "ClaudeClassifier",
    "Klassifikation",
    "BelegPipeline",
]
