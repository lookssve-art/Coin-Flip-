"""Tests fuer proaktive Benachrichtigungen (Meldungslogik + Versand)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.interface import baue_meldungen, TelegramNotifier
from src.models import ReviewItem


def _item(i, grund="Vorsteuer unklar", bezug="B-1"):
    return ReviewItem(id=i, grund=grund, bezug=bezug)


def _snapshot(ku_warn=False, oss_ueber=False):
    return {"schwellen": {
        "ku_laufend": {"aktuell": "85000", "grenze": "100000", "prozent": "85.0",
                       "warnung": ku_warn, "ueberschritten": False},
        "oss": {"aktuell": "12000" if oss_ueber else "100", "grenze": "10000",
                "prozent": "120.0" if oss_ueber else "1.0",
                "warnung": oss_ueber, "ueberschritten": oss_ueber},
    }}


class TestBaueMeldungen(unittest.TestCase):
    def test_neuer_fall_wird_gemeldet_und_gemerkt(self):
        texte, state = baue_meldungen([_item("REV-00001")], _snapshot(), {})
        self.assertTrue(any("REV-00001" in t for t in texte))
        self.assertIn("REV-00001", state["notified"])

    def test_bekannter_fall_nicht_erneut(self):
        state0 = {"notified": ["REV-00001"], "schwellen_gewarnt": {"ku_laufend": False, "oss": False}}
        texte, _ = baue_meldungen([_item("REV-00001")], _snapshot(), state0)
        self.assertEqual(texte, [])

    def test_aufgeloeste_faelle_fallen_aus_dem_zustand(self):
        state0 = {"notified": ["REV-00001"], "schwellen_gewarnt": {}}
        # Fall nicht mehr offen -> aus notified entfernt
        _, state = baue_meldungen([], _snapshot(), state0)
        self.assertNotIn("REV-00001", state["notified"])

    def test_schwelle_nur_bei_uebergang(self):
        # ok -> Warnung: meldet
        texte1, state1 = baue_meldungen([], _snapshot(ku_warn=True), {})
        self.assertTrue(any("§19" in t for t in texte1))
        # weiterhin Warnung: meldet nicht erneut
        texte2, _ = baue_meldungen([], _snapshot(ku_warn=True), state1)
        self.assertEqual(texte2, [])

    def test_oss_ueberschreitung_symbol(self):
        texte, _ = baue_meldungen([], _snapshot(oss_ueber=True), {})
        self.assertTrue(any("OSS-Fernverkauf" in t and "🔴" in t for t in texte))


class TestNotifierVersand(unittest.TestCase):
    def test_sendet_an_alle_chats(self):
        calls = []
        def fake(url, method=None, payload=None, **kw):
            calls.append(payload)
            return {"ok": True}
        n = TelegramNotifier("TOKEN", [111, 222], _sender=fake)
        anzahl = n.sende("Hallo")
        self.assertEqual(anzahl, 2)
        self.assertEqual({c["chat_id"] for c in calls}, {111, 222})
        self.assertEqual(calls[0]["text"], "Hallo")

    def test_fehler_bei_einem_chat_stoppt_nicht(self):
        def fake(url, method=None, payload=None, **kw):
            if payload["chat_id"] == 111:
                raise RuntimeError("boom")
            return {"ok": True}
        n = TelegramNotifier("TOKEN", [111, 222], _sender=fake)
        self.assertEqual(n.sende("x"), 1)   # 222 kam durch


if __name__ == "__main__":
    unittest.main(verbosity=2)
