"""Proaktive Telegram-Benachrichtigungen.

Nach jedem Pipeline-Lauf meldet der Agent von sich aus neue Freigabe-Faelle und
neu eintretende Schwellen-Warnungen an die freigeschalteten Nutzer — statt dass
jemand pollen muss. Ein Zustands-Dict (``notified``/``schwellen_gewarnt``)
verhindert Doppel-Meldungen: jeder Fall wird genau einmal gemeldet, eine
Schwellen-Warnung nur beim Wechsel ok -> Warnung.

Die Meldungslogik (``baue_meldungen``) ist rein und damit testbar; das Senden
(``TelegramNotifier``) ist davon getrennt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..util.http import http_json

_API = "https://api.telegram.org/bot{token}/sendMessage"

_SCHWELLEN = (("ku_laufend", "§19 laufend"), ("oss", "OSS-Fernverkauf"))


def baue_meldungen(offene_items: list, snapshot: dict, state: dict) -> tuple[list[str], dict]:
    """Erzeugt faellige Meldungen + den fortgeschriebenen Zustand (rein, kein Netzwerk).

    ``offene_items``: aktuell offene ReviewItem-Objekte.
    ``snapshot``: Dashboard-Snapshot (mit ``schwellen``).
    ``state``: {"notified": [ids], "schwellen_gewarnt": {key: bool}}.
    """
    notified = set(state.get("notified", []))
    gewarnt = dict(state.get("schwellen_gewarnt", {}))
    texte: list[str] = []
    neu_notified = set(notified)

    # Offene Faelle, die noch nicht gemeldet wurden.
    offen_ids = {i.id for i in offene_items}
    for item in offene_items:
        if item.id not in notified:
            texte.append(f"🔔 Neuer Freigabe-Fall {item.id}: {item.grund} "
                         f"(Bezug {item.bezug}). Mit /review pruefen.")
            neu_notified.add(item.id)

    # Aufgeloeste Faelle aus dem notified-Set entfernen (haelt es klein und erlaubt
    # erneute Meldung, falls derselbe Fall spaeter wieder offen auftaucht).
    neu_notified &= offen_ids

    # Schwellen: nur beim Uebergang ok -> Warnung/Ueberschreitung melden.
    neu_gewarnt = dict(gewarnt)
    sch = snapshot.get("schwellen", {})
    for key, label in _SCHWELLEN:
        d = sch.get(key, {})
        if not d:
            continue
        aktiv = bool(d.get("warnung") or d.get("ueberschritten"))
        if aktiv and not gewarnt.get(key):
            symbol = "🔴" if d.get("ueberschritten") else "🟡"
            texte.append(f"{symbol} Schwelle {label}: {d.get('aktuell')}/{d.get('grenze')} "
                         f"EUR ({d.get('prozent')}%). Mit /schwellen ansehen.")
        neu_gewarnt[key] = aktiv

    return texte, {"notified": sorted(neu_notified), "schwellen_gewarnt": neu_gewarnt}


@dataclass
class TelegramNotifier:
    token: str
    chat_ids: list
    _sender: Callable[..., dict] = field(default=http_json, repr=False)

    def sende(self, text: str) -> int:
        """Sendet ``text`` an alle freigeschalteten Chats. Rueckgabe: Anzahl Sends."""
        n = 0
        url = _API.format(token=self.token)
        for cid in self.chat_ids:
            try:
                self._sender(url, method="POST", payload={"chat_id": cid, "text": text})
                n += 1
            except Exception:  # noqa: BLE001 - eine fehlgeschlagene DM darf den Lauf nicht stoppen
                continue
        return n
