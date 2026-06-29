"""Tests fuer den config.yaml-Setup der Rechnungs-Absenderdaten (run.py-Helfer)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml
import run


class TestRechnungBlock(unittest.TestCase):
    def test_block_ist_gueltiges_yaml_mit_umlauten(self):
        block = run._rechnung_block(name="Max Mustermann",
                                    strasse="Marktstraße 9a", plz="80331",
                                    ort="München", steuernummer="")
        c = yaml.safe_load(block)
        a = c["rechnung"]["absender"]
        self.assertEqual(a["name"], "Max Mustermann")
        self.assertEqual(a["strasse"], "Marktstraße 9a")
        self.assertEqual(a["ort"], "München")
        self.assertEqual(a["steuernummer"], "")
        self.assertFalse(c["rechnung"]["lexware"]["finalize"])

    def test_anfuehrungszeichen_escaped(self):
        block = run._rechnung_block(name='Firma "X" GmbH')
        c = yaml.safe_load(block)
        self.assertEqual(c["rechnung"]["absender"]["name"], 'Firma "X" GmbH')


class TestFeldSetzen(unittest.TestCase):
    def test_nur_zielfeld_im_absender(self):
        txt = run._rechnung_block(name="Alt", steuernummer="")
        # name existiert in absender; steuernummer leer -> setzen
        neu = run._absender_feld_setzen(txt, "steuernummer", "143/123/45678")
        c = yaml.safe_load(neu)
        self.assertEqual(c["rechnung"]["absender"]["steuernummer"], "143/123/45678")
        self.assertEqual(c["rechnung"]["absender"]["name"], "Alt")

    def test_kein_absender_block_unveraendert(self):
        txt = "unternehmen:\n  name: x\n"
        self.assertEqual(run._absender_feld_setzen(txt, "name", "y"), txt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
