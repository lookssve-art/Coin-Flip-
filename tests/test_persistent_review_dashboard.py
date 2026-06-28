"""Tests: persistente Review-Queue (geteilt) + Bot-Dashboard (/report, /schwellen)."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.review import ReviewQueue
from src.interface import TelegramBot
from src.wissen import Duden


class TestPersistentQueue(unittest.TestCase):
    def test_persistenz_ueber_instanzen(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "rq.json")
            q1 = ReviewQueue(path=p)
            item = q1.add("Import + Einfuhrumsatzsteuer", "vorgang-1")
            # Zweite Instanz (anderer "Prozess") sieht den Fall.
            q2 = ReviewQueue(path=p)
            self.assertEqual(len(q2.offen()), 1)
            q2.aufloesen(item.id, freigeben=True, von="chef")
            # Erste Instanz nach reload sieht die Aufloesung.
            q1.reload()
            self.assertEqual(len(q1.offen()), 0)

    def test_idempotenz_kein_doppelter_fall(self):
        with tempfile.TemporaryDirectory() as d:
            q = ReviewQueue(path=os.path.join(d, "rq.json"))
            q.add("Vorsteuer unklar", "B-1")
            q.add("Vorsteuer unklar", "B-1")   # gleicher offener Fall -> nicht erneut
            self.assertEqual(len(q.offen()), 1)

    def test_ids_fortlaufend_nach_reload(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "rq.json")
            a = ReviewQueue(path=p).add("Grund A", "B-1")
            b = ReviewQueue(path=p).add("Grund B", "B-2")
            self.assertNotEqual(a.id, b.id)   # zweiter Prozess vergibt naechste ID


class TestBotDashboard(unittest.TestCase):
    def _bot(self, status_path=""):
        return TelegramBot(token="x", review_queue=ReviewQueue(),
                           allowed_user_ids={1}, duden=Duden(), status_path=status_path)

    def test_report_ohne_sync(self):
        antwort = self._bot().handle_command("/report", user_id=1)
        self.assertIn("Noch kein Sync", antwort)

    def test_report_mit_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "status.json")
            with open(p, "w", encoding="utf-8") as fh:
                json.dump({
                    "belege": 3, "banktransaktionen": 5, "verkaeufe": 4,
                    "differenz_ust": "7.98", "kleinunternehmer": True,
                    "ustva_zahllast": None, "review_offen": 2,
                    "schwellen": {
                        "ku_laufend": {"aktuell": "85000", "grenze": "100000",
                                       "prozent": "85.0", "warnung": True, "ueberschritten": False},
                        "oss": {"aktuell": "100", "grenze": "10000",
                                "prozent": "1.0", "warnung": False, "ueberschritten": False},
                    }}, fh)
            antwort = self._bot(status_path=p).handle_command("/report", user_id=1)
            self.assertIn("eBay-Verkaeufe: 4", antwort)
            self.assertIn("7.98", antwort)
            self.assertIn("Warnung", antwort)        # §19 bei 85 %
            self.assertIn("ok", antwort)             # OSS

    def test_schwellen_command(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "status.json")
            with open(p, "w", encoding="utf-8") as fh:
                json.dump({"schwellen": {"oss": {"aktuell": "12000", "grenze": "10000",
                          "prozent": "120.0", "warnung": True, "ueberschritten": True}}}, fh)
            antwort = self._bot(status_path=p).handle_command("/schwellen", user_id=1)
            self.assertIn("ueberschritten", antwort)


if __name__ == "__main__":
    unittest.main(verbosity=2)
