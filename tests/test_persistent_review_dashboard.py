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

    def test_uebersicht_ohne_daten(self):
        antwort = self._bot().handle_command("/uebersicht", user_id=1)
        self.assertIn("Steuer-Assistent", antwort)
        self.assertIn("Offene Freigaben", antwort)
        self.assertIn("Noch kein Durchlauf", antwort)

    def test_uebersicht_mit_daten(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "status.json")
            with open(p, "w", encoding="utf-8") as fh:
                json.dump({"belege": 4, "banktransaktionen": 12, "verkaeufe": 9,
                           "differenz_ust": "31.85", "kleinunternehmer": True,
                           "ustva_zahllast": None, "euer_gewinn": "742.50",
                           "euer_einnahmen": "1310.00", "euer_ausgaben": "567.50",
                           "review_offen": 0, "schwellen": {}}, fh)
            antwort = self._bot(status_path=p).handle_command("/uebersicht", user_id=1)
            self.assertIn("Gewinn 742.50 EUR", antwort)
            self.assertIn("Kleinunternehmer", antwort)

    def test_selbst_freischaltung_erster_nutzer(self):
        with tempfile.TemporaryDirectory() as d:
            owner = os.path.join(d, "owner.json")
            bot = TelegramBot(token="x", review_queue=ReviewQueue(),
                              duden=Duden(), owner_store=owner)   # leere Allowlist
            # Erster Nutzer wird automatisch freigeschaltet.
            antwort = bot.handle_command("hallo", user_id=555)
            self.assertIn("freigeschaltet", antwort)
            self.assertIn(555, bot.allowed_user_ids)
            self.assertTrue(os.path.exists(owner))
            # Zweiter, unbekannter Nutzer NICHT mehr.
            antwort2 = bot.handle_command("/uebersicht", user_id=999)
            self.assertIn("Nicht autorisiert", antwort2)
            # Neue Bot-Instanz laedt den Eigentuemer aus der Datei.
            bot2 = TelegramBot(token="x", review_queue=ReviewQueue(),
                               duden=Duden(), owner_store=owner)
            self.assertIn(555, bot2.allowed_user_ids)

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
