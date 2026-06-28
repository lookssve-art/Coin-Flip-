"""Telegram-Bot als Freigabe-/Review-Interface (MVP-Punkt 7).

Der Bot ist das Human-in-the-Loop-Frontend: er listet offene ``REVIEW_REQUIRED``-
Faelle und nimmt Freigabe/Ablehnung entgegen. Jede Entscheidung wird im Audit-Log
protokolliert (GoBD-Nachvollziehbarkeit).

Sicherheit: der Bot steuert Buchhaltungs-Freigaben — nur Chat-/User-IDs aus der
Allowlist duerfen Befehle ausfuehren. Ohne Allowlist werden Kommandos abgelehnt.

Die HTTP-Schicht nutzt urllib (siehe util.http), damit keine Zusatzpakete noetig
sind. ``handle_command`` ist bewusst rein (ohne Netzwerk) und damit testbar.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from ..audit import AuditLog
from ..review import ReviewQueue
from ..util.http import http_json, HttpError
from ..wissen import Duden

_API = "https://api.telegram.org/bot{token}/{method}"

_HELP = (
    "SERO Steuer-Assistent — Befehle:\n"
    "/review  — offene Freigabe-Faelle anzeigen\n"
    "/approve <ID>  — Fall freigeben (z. B. /approve REV-00001)\n"
    "/reject <ID>   — Fall ablehnen\n"
    "/status  — Kurzueberblick (offene Faelle)\n"
    "/report  — Dashboard: Umsaetze, USt, Schwellen aus dem letzten Sync\n"
    "/schwellen — § 19- und OSS-Schwellen-Status\n"
    "/duden <frage> — Steuer-/Buchhaltungswissen nachschlagen (A-Z)\n"
    "/help    — diese Hilfe\n\n"
    "Hinweis: Der Assistent bereitet vor — die steuerliche Verantwortung bleibt "
    "bei dir. Keine ELSTER-Abgabe ohne deine Freigabe. /duden ist allgemeine "
    "Information, keine Steuerberatung."
)

_DUDEN_SYSTEM = (
    "Du bist ein deutscher Steuer-/Buchhaltungs-Assistent (Rechtsstand 2025/2026). "
    "Beantworte die Frage NUR auf Basis des bereitgestellten Kontexts. Erfinde keine "
    "Paragraphen oder Zahlen. Wenn der Kontext nicht ausreicht, sage das und verweise "
    "auf den Steuerberater. Antworte praezise auf Deutsch, nenne die Fundstelle."
)


@dataclass
class TelegramBot:
    token: str
    review_queue: ReviewQueue
    audit_log: Optional[AuditLog] = None
    allowed_user_ids: set[int] = field(default_factory=set)
    duden: Optional[Duden] = None
    llm_api_key: str = ""
    llm_model: str = "claude-opus-4-8"
    status_path: str = ""
    _offset: int = 0

    # ------------------------------------------------------------------ #
    # Netzwerk
    # ------------------------------------------------------------------ #
    def _call(self, method: str, **params) -> dict:
        url = _API.format(token=self.token, method=method)
        return http_json(url, method="POST", payload=params)

    def get_me(self) -> dict:
        """Verifiziert den Token (Telegram getMe)."""
        return self._call("getMe")

    def send_message(self, chat_id: int, text: str) -> dict:
        return self._call("sendMessage", chat_id=chat_id, text=text)

    # ------------------------------------------------------------------ #
    # Befehlslogik (rein, testbar)
    # ------------------------------------------------------------------ #
    def ist_autorisiert(self, user_id: int) -> bool:
        # Leere Allowlist = niemand autorisiert (fail-safe).
        return user_id in self.allowed_user_ids

    def handle_command(self, text: str, user_id: int) -> str:
        """Verarbeitet eine Textnachricht und gibt die Antwort zurueck (kein Netzwerk)."""
        if not self.ist_autorisiert(user_id):
            return ("Nicht autorisiert. Diese Chat-ID ist nicht freigeschaltet. "
                    f"(Deine User-ID: {user_id} — in config.yaml unter "
                    "interface.telegram.allowed_user_ids eintragen.)")

        text = (text or "").strip()
        cmd, _, arg = text.partition(" ")
        cmd = cmd.lower()
        arg = arg.strip()

        if cmd in ("/start", "/help"):
            return _HELP
        # Vor Queue-Operationen den geteilten Store neu laden (Pipeline schreibt parallel).
        if cmd in ("/review", "/status", "/approve", "/reject"):
            self.review_queue.reload()
        if cmd == "/review":
            return self._cmd_review()
        if cmd == "/status":
            return self._cmd_status()
        if cmd == "/report":
            return self._cmd_report()
        if cmd == "/schwellen":
            return self._cmd_schwellen()
        if cmd == "/approve":
            return self._cmd_resolve(arg, freigeben=True, von=str(user_id))
        if cmd == "/reject":
            return self._cmd_resolve(arg, freigeben=False, von=str(user_id))
        if cmd == "/duden":
            return self._cmd_duden(arg)
        return "Unbekannter Befehl. /help fuer die Liste."

    def _lade_status(self) -> Optional[dict]:
        import json
        import os
        if not self.status_path or not os.path.exists(self.status_path):
            return None
        try:
            with open(self.status_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None

    def _cmd_report(self) -> str:
        s = self._lade_status()
        if s is None:
            return "Noch kein Sync-Lauf vorhanden. Pipeline (`run-all`/`sync`) ausfuehren."
        ku = s.get("kleinunternehmer")
        ust = ("Kleinunternehmer (§19): keine USt-Zahllast"
               if ku else f"USt-VA-Zahllast (Entwurf): {s.get('ustva_zahllast')} EUR")
        return (
            "📊 *Letzter Sync*\n"
            f"Belege: {s.get('belege')} | Bank: {s.get('banktransaktionen')} | "
            f"eBay-Verkaeufe: {s.get('verkaeufe')}\n"
            f"§25a-USt aus Marge: {s.get('differenz_ust')} EUR\n"
            f"{ust}\n"
            f"Offene Freigaben: {s.get('review_offen')}\n\n"
            + self._schwellen_text(s))

    def _cmd_schwellen(self) -> str:
        s = self._lade_status()
        if s is None:
            return "Noch kein Sync-Lauf vorhanden."
        return self._schwellen_text(s)

    @staticmethod
    def _schwellen_text(s: dict) -> str:
        sch = s.get("schwellen", {})
        zeilen = ["*Schwellen*"]
        for key, label in (("ku_laufend", "§19 laufend"), ("oss", "OSS-Fernverkauf")):
            d = sch.get(key, {})
            if not d:
                continue
            flag = ("🔴 ueberschritten" if d.get("ueberschritten")
                    else ("🟡 Warnung" if d.get("warnung") else "🟢 ok"))
            zeilen.append(f"{label}: {d.get('aktuell')}/{d.get('grenze')} EUR "
                          f"({d.get('prozent')}%) {flag}")
        return "\n".join(zeilen)

    def _cmd_duden(self, frage: str) -> str:
        if self.duden is None:
            return "Wissensbasis nicht geladen."
        if not frage:
            return ("Themen (A-Z):\n• " + "\n• ".join(self.duden.liste())
                    + "\n\nFrage stellen: /duden <frage>")
        hits = self.duden.suche(frage)
        if not hits:
            return ("Dazu habe ich nichts in der Wissensbasis. Bei konkreten Faellen "
                    "bitte den Steuerberater fragen.")
        # Wenn Claude konfiguriert ist: gegroundete Antwort; sonst die KB-Eintraege.
        if self.llm_api_key:
            try:
                return self._duden_claude(frage, hits)
            except Exception:  # noqa: BLE001 - Fallback auf KB
                pass
        return "\n\n———\n\n".join(self.duden.formatiere(h) for h in hits[:2])

    def _duden_claude(self, frage: str, hits) -> str:
        import anthropic  # lazy
        kontext = "\n\n".join(f"[{h.schlagwort} | {h.quelle}]\n{h.text}" for h in hits)
        client = anthropic.Anthropic(api_key=self.llm_api_key)
        resp = client.messages.create(
            model=self.llm_model, max_tokens=1024, system=_DUDEN_SYSTEM,
            output_config={"effort": "low"},
            messages=[{"role": "user",
                       "content": f"Kontext:\n{kontext}\n\nFrage: {frage}"}],
        )
        text = next((b.text for b in resp.content if b.type == "text"), "")
        return text or "\n\n".join(self.duden.formatiere(h) for h in hits[:2])

    def _cmd_review(self) -> str:
        offen = self.review_queue.offen()
        if not offen:
            return "Keine offenen Freigabe-Faelle. ✅"
        zeilen = ["Offene Freigabe-Faelle:"]
        for item in offen:
            zeilen.append(f"• {item.id} — {item.grund} (Bezug: {item.bezug})")
        zeilen.append("\nFreigeben: /approve <ID>  |  Ablehnen: /reject <ID>")
        return "\n".join(zeilen)

    def _cmd_status(self) -> str:
        offen = self.review_queue.offen()
        return (f"Status: {len(offen)} offene Freigabe-Faelle.\n"
                "Alle finalisierenden Schritte (Festschreibung, USt-VA) erfordern "
                "deine Freigabe.")

    def _cmd_resolve(self, item_id: str, *, freigeben: bool, von: str) -> str:
        item_id = item_id.strip()
        if not item_id:
            return "Bitte ID angeben, z. B. /approve REV-00001"
        item = self.review_queue.aufloesen(item_id, freigeben=freigeben, von=von)
        if item is None:
            return f"Kein Fall mit ID {item_id} gefunden."
        aktion = "freigegeben" if freigeben else "abgelehnt"
        if self.audit_log is not None:
            self.audit_log.append(
                "review.aufgeloest",
                {"item": item_id, "aktion": aktion, "von": von, "grund": item.grund},
            )
        return f"{item_id} {aktion}. ({item.grund})"

    # ------------------------------------------------------------------ #
    # Long-Polling-Schleife
    # ------------------------------------------------------------------ #
    def _verarbeite_update(self, update: dict) -> None:
        msg = update.get("message") or update.get("edited_message")
        if not msg:
            return
        text = msg.get("text", "")
        if not text:
            return
        chat_id = msg["chat"]["id"]
        user_id = (msg.get("from") or {}).get("id", 0)
        antwort = self.handle_command(text, user_id)
        try:
            self.send_message(chat_id, antwort)
        except HttpError as exc:  # pragma: no cover - Netzwerk
            print(f"[telegram] sendMessage fehlgeschlagen: {exc}")

    def poll_once(self, timeout: int = 30) -> int:
        """Holt anstehende Updates (long polling) und verarbeitet sie. Rueckgabe: Anzahl."""
        resp = self._call("getUpdates", offset=self._offset, timeout=timeout)
        updates = resp.get("result", [])
        for upd in updates:
            self._offset = max(self._offset, upd["update_id"] + 1)
            self._verarbeite_update(upd)
        return len(updates)

    def run(self, *, poll_timeout: int = 30, pause: float = 1.0) -> None:  # pragma: no cover
        """Blockierende Endlosschleife (Ctrl-C zum Beenden)."""
        me = self.get_me().get("result", {})
        print(f"[telegram] Bot @{me.get('username', '?')} laeuft. Strg-C zum Beenden.")
        while True:
            try:
                if self.poll_once(poll_timeout) == 0:
                    time.sleep(pause)
            except KeyboardInterrupt:
                print("\n[telegram] beendet.")
                return
            except Exception as exc:  # noqa: BLE001 - robuste Schleife
                print(f"[telegram] Fehler: {exc}; warte 5s")
                time.sleep(5)
