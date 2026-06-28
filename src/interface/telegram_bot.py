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

_API = "https://api.telegram.org/bot{token}/{method}"

_HELP = (
    "SERO Steuer-Assistent — Befehle:\n"
    "/review  — offene Freigabe-Faelle anzeigen\n"
    "/approve <ID>  — Fall freigeben (z. B. /approve REV-00001)\n"
    "/reject <ID>   — Fall ablehnen\n"
    "/status  — Kurzueberblick\n"
    "/help    — diese Hilfe\n\n"
    "Hinweis: Der Assistent bereitet vor — die steuerliche Verantwortung bleibt "
    "bei dir. Keine ELSTER-Abgabe ohne deine Freigabe."
)


@dataclass
class TelegramBot:
    token: str
    review_queue: ReviewQueue
    audit_log: Optional[AuditLog] = None
    allowed_user_ids: set[int] = field(default_factory=set)
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
        if cmd == "/review":
            return self._cmd_review()
        if cmd == "/status":
            return self._cmd_status()
        if cmd == "/approve":
            return self._cmd_resolve(arg, freigeben=True, von=str(user_id))
        if cmd == "/reject":
            return self._cmd_resolve(arg, freigeben=False, von=str(user_id))
        return "Unbekannter Befehl. /help fuer die Liste."

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
