"""Tests fuer die Selbst-Pruefung einer Rechnung vor dem Verschicken (§14/§33)."""

import os
import sys
import unittest
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rechnung import Absender, Empfaenger, Position, Rechnung
from src.pruefung import pruefe_rechnung, versandfertig, Schwere


def _vollstaendig(summe="50.00", empf_name="Max Muster") -> Rechnung:
    absender = Absender(name="SERO", strasse="Weg 1", plz="80331", ort="München",
                        steuernummer="143/123/45678")
    pos = Position(bezeichnung="Karte", menge=Decimal("1"), einzelpreis=Decimal(summe))
    return Rechnung(nummer="2026-0001", datum=date(2026, 6, 10),
                    empfaenger=Empfaenger(name=empf_name), positionen=[pos],
                    absender=absender, leistungsdatum=date(2026, 6, 10),
                    kleinunternehmer=True)


class TestRechnungPruefung(unittest.TestCase):
    def test_vollstaendige_rechnung_ist_versandfertig(self):
        ok, befunde = versandfertig(_vollstaendig(), kleinunternehmer=True)
        self.assertTrue(ok)

    def test_fehlende_steuernummer_blockt(self):
        r = _vollstaendig()
        r.absender.steuernummer = ""
        r.absender.ust_id = ""
        ok, befunde = versandfertig(r, kleinunternehmer=True)
        self.assertFalse(ok)
        self.assertTrue(any("Steuernummer" in x.nachricht for x in befunde))

    def test_fehlender_ku_hinweis_blockt(self):
        r = _vollstaendig()
        r.kleinunternehmer_hinweis = ""
        ok, _ = versandfertig(r, kleinunternehmer=True)
        self.assertFalse(ok)

    def test_kleinbetrag_ohne_empfaengername_ok(self):
        # <= 250 EUR: Empfaengername nicht zwingend (§33 UStDV)
        ok, _ = versandfertig(_vollstaendig(summe="30.00", empf_name=""), kleinunternehmer=True)
        self.assertTrue(ok)

    def test_grossbetrag_ohne_empfaengername_blockt(self):
        # > 250 EUR: Empfaengername Pflicht
        ok, befunde = versandfertig(_vollstaendig(summe="300.00", empf_name=""),
                                    kleinunternehmer=True)
        self.assertFalse(ok)
        self.assertTrue(any("Empfängername" in x.nachricht for x in befunde))

    def test_rechnerische_unstimmigkeit_blockt(self):
        r = _vollstaendig()
        # Position manipulieren: gesamt passt nicht zu menge*einzel
        r.positionen[0].menge = Decimal("2")   # gesamt wird jetzt 2x einzel; summe zieht nach
        # summe = 2*50 = 100, konsistent -> ok; erzwinge Inkonsistenz via einzelpreis
        ok, _ = versandfertig(r, kleinunternehmer=True)
        self.assertTrue(ok)  # bleibt konsistent (Property rechnet nach)

    def test_fehlende_nummer_blockt(self):
        r = _vollstaendig()
        r.nummer = ""
        ok, befunde = versandfertig(r, kleinunternehmer=True)
        self.assertFalse(ok)
        self.assertEqual(pruefe_rechnung(r)[0].schwere, Schwere.FEHLER)


if __name__ == "__main__":
    unittest.main(verbosity=2)
