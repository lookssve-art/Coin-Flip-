#!/usr/bin/env python3
"""SERO Accounting Agent — CLI-Einstieg (MVP-Demo).

Verdrahtet die Compliance-Fundament-Module zu einem nachvollziehbaren Durchlauf.
Dies ist KEINE Steuerabgabe — alle Ausgaben sind Entwuerfe (siehe Spezifikation
Abschnitt 0/9/10).

Verwendung:
    python run.py demo                 # End-to-End-Demo der Module
    python run.py verfahrensdoku       # Verfahrensdokumentation erzeugen
    python run.py audit-verify         # Hash-Kette des Audit-Logs pruefen
    python run.py telegram-check       # Telegram-Bot-Token verifizieren (getMe)
    python run.py telegram             # Telegram-Bot starten (Freigabe-Interface)
    python run.py ebay-auth            # eBay-Consent-URL ausgeben (OAuth-Flow starten)
    python run.py ebay-token <code>    # Authorization-Code gegen Refresh-Token tauschen
    python run.py ebay-sync [tage]     # eBay-Transaktionen abrufen + Reconciliation-Import
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal

try:
    import yaml
except ImportError:  # pragma: no cover - YAML ist optional fuer die Demo
    yaml = None

from src.audit import AuditLog
from src.review import ReviewQueue, pruefe_review_trigger
from src.tax import SchwellenMonitor, einzeldifferenz, ustva_vorbereitung
from src.verfahrensdoku import generiere_verfahrensdoku

CONFIG_PATH = "config.yaml"
EXAMPLE_CONFIG_PATH = "config.example.yaml"


def lade_config() -> dict:
    path = CONFIG_PATH if os.path.exists(CONFIG_PATH) else EXAMPLE_CONFIG_PATH
    if yaml is None:
        return _fallback_config()
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _fallback_config() -> dict:
    return {
        "unternehmen": {"name": "SERO Handel", "finanzamt": "Muenchen",
                        "bundesland": "Bayern", "rechtsform": "einzelunternehmen",
                        "gewinnermittlung": "euer"},
        "steuer": {"kleinunternehmer": True},
        "aufbewahrung": {"buchungsbelege_jahre": 8, "buecher_jahresabschluss_jahre": 10,
                         "geschaeftsbriefe_jahre": 6},
        "pfade": {"audit_log": "audit/audit_log.jsonl", "belegspeicher": "belege/",
                  "verfahrensdoku": "docs/verfahrensdokumentation.md"},
        "schwellen": {"warnung_ab_prozent": 80},
        "review": {"betragsschwelle_eur": 2000},
    }


def cmd_demo(config: dict) -> int:
    print("== SERO Accounting Agent — Demo ==\n")
    ku = bool(config.get("steuer", {}).get("kleinunternehmer", True))

    # 1) Audit-Log (append-only, hash-verkettet)
    log = AuditLog(config["pfade"]["audit_log"])
    log.append("demo.start", {"hinweis": "Demo-Durchlauf, keine Steuerabgabe"})

    # 2) Differenzbesteuerung § 25a (Pokemon-Karte aus Privatankauf)
    marge = einzeldifferenz(Decimal("120"), Decimal("70"), Decimal("19"))
    print(f"[§25a] Verkauf 120 / Einkauf 70 -> Marge {marge.marge} "
          f"(netto {marge.netto_marge}, USt {marge.ust_betrag})")
    log.append("verkauf.differenz", {"marge": str(marge.marge), "ust": str(marge.ust_betrag)})

    # 3) Schwellen-Monitoring mit Fruehwarnung
    mon = SchwellenMonitor(warnung_ab_prozent=Decimal(str(
        config.get("schwellen", {}).get("warnung_ab_prozent", 80))))
    status = mon.kleinunternehmer_laufend(Decimal("85000"))
    flag = "WARNUNG" if status.warnung else "ok"
    print(f"[Schwelle] KU laufend {status.aktuell}/{status.grenze} EUR "
          f"= {status.prozent}% [{flag}]")

    # 4) Review-Queue (Human-in-the-Loop)
    queue = ReviewQueue()
    gruende = pruefe_review_trigger(
        schwelle_naht=status.warnung,
        betrag_brutto=Decimal("2500"),
        betragsschwelle=Decimal(str(config.get("review", {}).get("betragsschwelle_eur", 2000))),
    )
    queue.add_many(gruende, bezug="demo-vorgang-1")
    print(f"[Review] {len(queue.offen())} offene Faelle: "
          f"{', '.join(i.grund for i in queue.offen()) or 'keine'}")
    log.append("review.erstellt", {"anzahl": len(queue.offen())})

    # 5) USt-VA-Vorbereitung (Entwurf!)
    report = ustva_vorbereitung(
        "Q2/2026", kleinunternehmer=ku,
        umsatzsteuer_je_satz={"19": Decimal("190")},
        differenz_ust=marge.ust_betrag, vorsteuer=Decimal("0"),
    )
    if ku:
        print(f"[USt-VA] {report.zeitraum}: {report.hinweise[0]}")
    else:
        print(f"[USt-VA] {report.zeitraum}: Zahllast {report.zahllast} EUR (ENTWURF)")

    # 6) Audit-Kette pruefen
    ok, fehler = log.verify()
    print(f"\n[Audit] {log.count()} Eintraege, Kette {'intakt' if ok else f'BRUCH @ {fehler}'}")
    return 0 if ok else 1


def cmd_verfahrensdoku(config: dict) -> int:
    md = generiere_verfahrensdoku(config)
    out = config.get("pfade", {}).get("verfahrensdoku", "docs/verfahrensdokumentation.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(md)
    print(f"Verfahrensdokumentation geschrieben: {out} ({len(md)} Zeichen)")
    return 0


def cmd_audit_verify(config: dict) -> int:
    log = AuditLog(config["pfade"]["audit_log"])
    ok, fehler = log.verify()
    print(f"Audit-Log: {log.count()} Eintraege — "
          f"{'Kette intakt' if ok else f'KETTENBRUCH bei Eintrag {fehler}'}")
    return 0 if ok else 1


def cmd_telegram_check(config: dict) -> int:
    from src.interface import TelegramBot
    from src.review import ReviewQueue
    tg = config.get("interface", {}).get("telegram", {})
    if not tg.get("token"):
        print("Kein Telegram-Token in config.yaml (interface.telegram.token).")
        return 2
    bot = TelegramBot(token=tg["token"], review_queue=ReviewQueue())
    try:
        me = bot.get_me().get("result", {})
    except Exception as exc:  # noqa: BLE001
        print(f"getMe fehlgeschlagen: {exc}")
        return 1
    print(f"Bot OK: @{me.get('username')} (id {me.get('id')}, name {me.get('first_name')})")
    return 0


def cmd_telegram(config: dict) -> int:
    from src.audit import AuditLog
    from src.interface import TelegramBot
    from src.review import ReviewQueue
    tg = config.get("interface", {}).get("telegram", {})
    if not tg.get("token"):
        print("Kein Telegram-Token in config.yaml (interface.telegram.token).")
        return 2
    allowed = set(tg.get("allowed_user_ids") or [])
    if not allowed:
        print("WARNUNG: allowed_user_ids leer — der Bot lehnt alle Befehle ab.\n"
              "Schreibe dem Bot eine Nachricht; er antwortet mit deiner User-ID,\n"
              "die du dann in config.yaml unter interface.telegram.allowed_user_ids eintraegst.")
    bot = TelegramBot(
        token=tg["token"],
        review_queue=ReviewQueue(),
        audit_log=AuditLog(config["pfade"]["audit_log"]),
        allowed_user_ids=allowed,
    )
    bot.run(poll_timeout=int(tg.get("poll_timeout", 30)))
    return 0


def _ebay_oauth(config: dict):
    from src.integrations import EbayOAuth
    e = config.get("integrationen", {}).get("ebay", {})
    fehlend = [k for k in ("app_id", "cert_id", "ru_name") if not e.get(k)]
    if fehlend:
        print(f"eBay-Config unvollstaendig: {', '.join(fehlend)} fehlen in config.yaml.")
        return None, e
    return EbayOAuth(app_id=e["app_id"], cert_id=e["cert_id"], ru_name=e["ru_name"],
                     environment=e.get("environment", "production")), e


def cmd_ebay_auth(config: dict) -> int:
    oauth, _ = _ebay_oauth(config)
    if oauth is None:
        return 2
    print("1) Oeffne diese URL im Browser und bestaetige den Zugriff:\n")
    print(oauth.consent_url(state="sero"))
    print("\n2) eBay leitet auf deine RuName-URL mit ?code=... weiter.")
    print("3) Fuehre dann aus:  python run.py ebay-token <code>")
    return 0


def cmd_ebay_token(config: dict, code: str = "") -> int:
    oauth, _ = _ebay_oauth(config)
    if oauth is None:
        return 2
    if not code:
        print("Bitte den Authorization-Code angeben: python run.py ebay-token <code>")
        return 2
    try:
        tok = oauth.exchange_code(code)
    except Exception as exc:  # noqa: BLE001
        print(f"Token-Austausch fehlgeschlagen: {exc}")
        return 1
    print("Refresh-Token erhalten. Trage ihn in config.yaml unter "
          "integrationen.ebay.refresh_token ein:\n")
    print(tok.refresh_token)
    print(f"\n(Access-Token gueltig ~{tok.expires_in}s; "
          f"Refresh-Token ~{tok.refresh_token_expires_in}s)")
    return 0


def cmd_ebay_sync(config: dict, tage: str = "30") -> int:
    from datetime import date, timedelta
    from src.integrations import EbayFinanceClient
    from src.imports import importiere_ebay_verkaeufe
    oauth, e = _ebay_oauth(config)
    if oauth is None:
        return 2
    if not e.get("refresh_token"):
        print("Kein refresh_token in config.yaml — zuerst `ebay-auth` + `ebay-token` ausfuehren.")
        return 2
    try:
        tok = oauth.refresh(e["refresh_token"])
        client = EbayFinanceClient(access_token=tok.access_token,
                                   marketplace_id=e.get("marketplace_id", "EBAY_DE"),
                                   environment=e.get("environment", "production"))
        ende = date.today()
        start = ende - timedelta(days=int(tage))
        roh = client.get_transactions(start=start, end=ende)
    except Exception as exc:  # noqa: BLE001
        print(f"eBay-Abruf fehlgeschlagen: {exc}")
        return 1
    rows = EbayFinanceClient.to_rows(roh)
    sales = importiere_ebay_verkaeufe(rows)
    print(f"eBay-Sync {start}..{ende}: {len(roh)} Transaktionen -> {len(sales)} Vorgaenge.")
    unklar = [r for r in rows if r.get("_review")]
    if unklar:
        print(f"  {len(unklar)} zur Pruefung markiert (unklarer Typ).")
    return 0


COMMANDS = {
    "demo": cmd_demo,
    "verfahrensdoku": cmd_verfahrensdoku,
    "audit-verify": cmd_audit_verify,
    "telegram-check": cmd_telegram_check,
    "telegram": cmd_telegram,
    "ebay-auth": cmd_ebay_auth,
    "ebay-token": cmd_ebay_token,
    "ebay-sync": cmd_ebay_sync,
}


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "demo"
    if cmd in ("-h", "--help", "help") or cmd not in COMMANDS:
        print(__doc__)
        return 0 if cmd in ("-h", "--help", "help") else 2
    config = lade_config()
    extra = argv[2:]
    if extra:
        return COMMANDS[cmd](config, *extra)
    return COMMANDS[cmd](config)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
