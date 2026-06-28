"""Tests fuer Telegram-Bot-Logik und Export (offline, ohne Netzwerk)."""

import os
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.audit import AuditLog
from src.export import RateLimiter, schreibe_buchungsjournal, schreibe_differenz_journal
from src.export.lexware import LexwareClient
from src.interface import TelegramBot
from src.reconciliation import MatchResult, MatchStatus
from src.review import ReviewQueue
from src.tax import einzeldifferenz


class TestTelegramBot(unittest.TestCase):
    def _bot(self, audit=None):
        q = ReviewQueue()
        q.add("Import + Einfuhrumsatzsteuer", "vorgang-1")
        return TelegramBot(token="x", review_queue=q, audit_log=audit,
                           allowed_user_ids={42}), q

    def test_nicht_autorisiert(self):
        bot, _ = self._bot()
        antwort = bot.handle_command("/review", user_id=999)
        self.assertIn("Nicht autorisiert", antwort)
        self.assertIn("999", antwort)  # zeigt die User-ID zum Eintragen

    def test_review_listet_offene(self):
        bot, _ = self._bot()
        antwort = bot.handle_command("/review", user_id=42)
        self.assertIn("REV-00001", antwort)
        self.assertIn("Einfuhrumsatzsteuer", antwort)

    def test_approve_protokolliert_audit(self):
        with tempfile.TemporaryDirectory() as d:
            log = AuditLog(os.path.join(d, "a.jsonl"))
            bot, q = self._bot(audit=log)
            antwort = bot.handle_command("/approve REV-00001", user_id=42)
            self.assertIn("freigegeben", antwort)
            self.assertEqual(len(q.offen()), 0)
            self.assertEqual(log.count(), 1)
            ok, _ = log.verify()
            self.assertTrue(ok)

    def test_unbekannte_id(self):
        bot, _ = self._bot()
        self.assertIn("Kein Fall", bot.handle_command("/approve REV-99999", user_id=42))


class TestRateLimiter(unittest.TestCase):
    def test_mindestabstand(self):
        schlafzeiten = []
        fake_now = iter([0.0, 0.0, 0.1, 0.1])  # zweiter Aufruf nur 0.1s spaeter
        rl = RateLimiter(max_pro_sekunde=2.0, _now=lambda: next(fake_now),
                         _sleep=schlafzeiten.append)
        rl.warte()  # erster Aufruf, kein Schlaf
        rl.warte()  # 0.1s seit last -> muss 0.4s warten
        self.assertEqual(len(schlafzeiten), 1)
        self.assertAlmostEqual(schlafzeiten[0], 0.4, places=5)


class TestLexwareValidierung(unittest.TestCase):
    def test_unzulaessiger_ust_satz(self):
        c = LexwareClient(api_key="x")
        with self.assertRaises(ValueError):
            c.validiere_ust_satz(Decimal("12"))
        c.validiere_ust_satz(Decimal("19"))  # zulaessig -> kein Fehler


class TestCsvExport(unittest.TestCase):
    def test_buchungsjournal(self):
        with tempfile.TemporaryDirectory() as d:
            pfad = os.path.join(d, "journal.csv")
            n = schreibe_buchungsjournal(pfad, [
                MatchResult("tx1", MatchStatus.MATCHED, "R1", Decimal("0"), 2026),
                MatchResult("tx2", MatchStatus.UNMATCHED, None, Decimal("0"), 2026,
                            ["Kein Beleg"]),
            ])
            self.assertEqual(n, 2)
            with open(pfad, encoding="utf-8") as fh:
                inhalt = fh.read()
            self.assertIn("transaction_id;status", inhalt)
            self.assertIn("matched", inhalt)

    def test_differenz_journal(self):
        with tempfile.TemporaryDirectory() as d:
            pfad = os.path.join(d, "diff.csv")
            m = einzeldifferenz(Decimal("120"), Decimal("70"))
            n = schreibe_differenz_journal(pfad, [("A1", m)])
            self.assertEqual(n, 1)
            with open(pfad, encoding="utf-8") as fh:
                inhalt = fh.read()
            self.assertIn("7.98", inhalt)  # herausgerechnete USt


if __name__ == "__main__":
    unittest.main(verbosity=2)
