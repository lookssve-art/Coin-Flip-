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
    python run.py ebay-kaeufe [export] # eBay-Kaufhistorie (JSON) -> Einkaufspreise (§25a)
    python run.py ebay-kaeufe-api      # Kaeufe der letzten ~90 Tage live via Trading-API holen
    python run.py ebay-signkey         # Ed25519-Signaturschluessel fuer Finances-API erstellen
    python run.py ebay-finances [tage] # ECHTE eBay-Gebuehren signiert abrufen (data/ebay_fees.json)
    python run.py rechnung-setup ...   # Absenderdaten in config.yaml schreiben (Firmenangaben)
    python run.py rechnungen           # Rechnungen aus eBay-Verkaeufen erzeugen (Billbee-Ersatz)
    python run.py rechnungen-push      # Erzeugte Rechnungen nach Lexware Office uebertragen
    python run.py buchhaltung          # ALLES: eBay->Rechnungen->Lexware->Gegenrechnung (1 Befehl)
    python run.py bwa                  # BWA/Monatsabschluss (Rohertrag, Kosten, Kennzahlen)
    python run.py pruefung             # Plausibilitaet (IBAN/USt-IdNr/Dubletten)
    python run.py kann                 # Funktionsumfang anzeigen (Master-Prompt-Abgleich)
    python run.py lexware-ping         # Lexware-API-Key verifizieren (/profile)
    python run.py bank-import <csv>    # Lexware-Geschaeftskonto-CSV importieren
    python run.py lexware-push <dir>   # Belege aus <dir> als Draft-Vouchers nach Lexware
    python run.py sync <belege> <csv>  # End-to-End: Belege+Bank -> Reconciliation -> Journal
    python run.py run-all               # Voller Pipeline-Durchlauf (kaeufe->sync->verbuchung)
    python run.py serve                 # Autonomer Dauerbetrieb: Bot + Pipeline im Takt
    python run.py check                 # Setup-Diagnose: was ist konfiguriert, was fehlt
    python run.py lexware-kategorien    # Lexware-Kategorie-UUIDs auflisten (fuer kategorie_map)
    python run.py gewinn [bank_csv]     # Einnahmen/Ausgaben/Gewinn seit Geschaeftsbeginn
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


def _bwa_text(config: dict) -> str:
    """BWA als Text fuer den Bot (nutzt den letzten EÜR-Snapshot)."""
    from src.abschluss import erstelle_bwa, render_bwa_text
    from src.util import ab_geschaeftsbeginn
    euer = _euer_snapshot(config)
    if euer is None:
        return "Noch kein Stand — erst /sync ausfuehren."
    beginn = _geschaeftsbeginn(config)
    sales = [s for s in _ebay_verkaeufe(config)
             if (not beginn or ab_geschaeftsbeginn(s.datum, beginn))]
    rahmen = config.get("kontierung", {}).get("rahmen", "skr03")
    return render_bwa_text(erstelle_bwa(sales, euer, rahmen=rahmen,
                                        config=config.get("kontierung")))


def _rechnungen_zusammenfassung(config: dict) -> str:
    """Erzeugt Rechnungen (+ optional Lexware-Push) und liefert eine kurze Meldung."""
    cmd_rechnungen(config)
    reg = _rechnungs_register(config)
    gesamt = len(reg.alle())
    offen_lex = len(reg.offene_lexware())
    teile = [f"{gesamt} Rechnungen im Register."]
    rc = _rechnung_config(config)
    if rc.get("lexware", {}).get("push") and \
            config.get("integrationen", {}).get("lexware_office", {}).get("api_key"):
        cmd_rechnungen_push(config)
        teile.append(f"{len(reg.offene_lexware())} noch offen für Lexware.")
    elif offen_lex:
        teile.append(f"{offen_lex} noch nicht in Lexware (push deaktiviert).")
    return " ".join(teile)


def cmd_telegram(config: dict) -> int:
    from src.audit import AuditLog
    from src.interface import TelegramBot
    from src.review import ReviewQueue
    tg = config.get("interface", {}).get("telegram", {})
    if not tg.get("token"):
        print("Kein Telegram-Token in config.yaml (interface.telegram.token).")
        return 2
    allowed = set(tg.get("allowed_user_ids") or [])
    owner_store = config.get("pfade", {}).get("telegram_owner", "data/telegram_owner.json")
    if not allowed and not os.path.exists(owner_store):
        print("Erst-Einrichtung: noch niemand freigeschaltet.\n"
              "Schreibe dem Bot jetzt eine Nachricht — der ERSTE Schreiber wird automatisch\n"
              "als Eigentuemer freigeschaltet (danach sind nur noch DU berechtigt).")
    from src.wissen import Duden
    llm = config.get("integrationen", {}).get("llm", {})
    bot = TelegramBot(
        token=tg["token"],
        review_queue=_review_queue(config),
        audit_log=AuditLog(config["pfade"]["audit_log"]),
        allowed_user_ids=allowed,
        duden=Duden(),
        llm_api_key=llm.get("api_key", ""),
        llm_model=llm.get("model", "claude-opus-4-8"),
        status_path=config.get("pfade", {}).get("status", ""),
        owner_store=owner_store,
        pipeline_callback=lambda: (cmd_run_all(config),
                                   "Zahlen aktualisiert.")[1],
        rechnungen_callback=lambda: _rechnungen_zusammenfassung(config),
        bwa_callback=lambda: _bwa_text(config),
    )
    bot.run(poll_timeout=int(tg.get("poll_timeout", 30)))
    return 0


def _ebay_oauth(config: dict, *, brauche_ru_name: bool = False):
    from src.integrations import EbayOAuth
    e = config.get("integrationen", {}).get("ebay", {})
    pflicht = ["app_id", "cert_id"] + (["ru_name"] if brauche_ru_name else [])
    fehlend = [k for k in pflicht if not e.get(k)]
    if fehlend:
        print(f"eBay-Config unvollstaendig: {', '.join(fehlend)} fehlen in config.yaml.")
        return None, e
    return EbayOAuth(app_id=e["app_id"], cert_id=e["cert_id"],
                     ru_name=e.get("ru_name", ""),
                     environment=e.get("environment", "production")), e


def cmd_ebay_auth(config: dict) -> int:
    oauth, _ = _ebay_oauth(config, brauche_ru_name=True)
    if oauth is None:
        return 2
    print("1) Oeffne diese URL im Browser und bestaetige den Zugriff:\n")
    print(oauth.consent_url(state="sero"))
    print("\n2) eBay leitet auf deine RuName-URL mit ?code=... weiter.")
    print("3) Fuehre dann aus:  python run.py ebay-token <code>")
    return 0


def cmd_ebay_token(config: dict, code: str = "") -> int:
    oauth, _ = _ebay_oauth(config, brauche_ru_name=True)
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
    if not tok.refresh_token:
        print("Kein Refresh-Token in der Antwort erhalten.")
        return 1
    gespeichert = _config_setze_ebay_refresh(tok.refresh_token)
    if gespeichert:
        print("\n✅ ERFOLG! Refresh-Token automatisch in config.yaml gespeichert.")
        print("   Jetzt nur noch den Bot neu starten:  bash start-bot.sh")
        print(f"   (gueltig ~{(tok.refresh_token_expires_in or 0)//86400} Tage)")
    else:
        print("Refresh-Token erhalten (config.yaml nicht gefunden — bitte manuell eintragen):\n")
        print(tok.refresh_token)
    return 0


def _yaml_escape(s: str) -> str:
    return str(s).replace("\\", "\\\\").replace('"', '\\"')


def _rechnung_block(name="", strasse="", plz="", ort="", steuernummer="",
                    ust_id="", iban="") -> str:
    e = _yaml_escape
    return (
        "\n# --- Rechnungsstellung (Billbee-Ersatz) — via `rechnung-setup` gesetzt ---\n"
        "rechnung:\n"
        "  aktiv: true\n"
        '  modus: "alle"\n'
        '  nummer_prefix: ""\n'
        "  nummer_mit_jahr: true\n"
        "  nummer_start: 1\n"
        '  kleinunternehmer_hinweis: "Gemäß § 19 UStG wird keine Umsatzsteuer '
        'berechnet (Kleinunternehmer)."\n'
        '  verzeichnis: "belege/rechnungen/"\n'
        '  register: "data/rechnungen_register.json"\n'
        '  nummernkreis: "data/rechnungsnummern.json"\n'
        "  lexware:\n"
        "    push: false\n"
        "    finalize: false\n"
        "    pdf_speichern: true\n"
        "  absender:\n"
        f'    name: "{e(name)}"\n'
        f'    strasse: "{e(strasse)}"\n'
        f'    plz: "{e(plz)}"\n'
        f'    ort: "{e(ort)}"\n'
        '    land: "DE"\n'
        f'    steuernummer: "{e(steuernummer)}"\n'
        f'    ust_id: "{e(ust_id)}"\n'
        '    email: ""\n'
        '    telefon: ""\n'
        f'    iban: "{e(iban)}"\n'
        '    bic: ""\n'
    )


def _absender_feld_setzen(txt: str, feld: str, wert: str) -> str:
    """Ersetzt EIN Feld im absender-Block (Zeilen nach 'absender:'), formaterhaltend."""
    import re
    idx = txt.find("\n  absender:")
    if idx < 0:
        return txt
    kopf, rest = txt[:idx], txt[idx:]
    neu, n = re.subn(rf'(?m)^(\s+{feld}:\s*).*$',
                     lambda m: m.group(1) + '"' + _yaml_escape(wert) + '"', rest, count=1)
    return kopf + (neu if n else rest)


def cmd_rechnung_setup(config: dict, name: str = "", strasse: str = "", plz: str = "",
                       ort: str = "", steuernummer: str = "", iban: str = "",
                       ust_id: str = "") -> int:
    """Schreibt die Absenderdaten in config.yaml — legt den rechnung-Block an
    (falls fehlt) oder aktualisiert die absender-Felder (falls vorhanden)."""
    path = "config.yaml"
    if not os.path.exists(path):
        print("config.yaml nicht gefunden (im Projektordner ausfuehren).")
        return 2
    with open(path, "r", encoding="utf-8") as fh:
        txt = fh.read()
    import re
    if re.search(r"(?m)^rechnung:", txt):
        # Block existiert -> nur die uebergebenen Felder aktualisieren.
        felder = {"name": name, "strasse": strasse, "plz": plz, "ort": ort,
                  "steuernummer": steuernummer, "iban": iban, "ust_id": ust_id}
        for feld, wert in felder.items():
            if wert:
                txt = _absender_feld_setzen(txt, feld, wert)
        aktion = "absender-Felder aktualisiert"
    else:
        if not txt.endswith("\n"):
            txt += "\n"
        txt += _rechnung_block(name, strasse, plz, ort, steuernummer, ust_id, iban)
        aktion = "rechnung-Block angelegt"
    # Sicherheits-Check: bleibt es gueltiges YAML?
    try:
        import yaml
        yaml.safe_load(txt)
    except Exception as exc:  # noqa: BLE001
        print(f"Abbruch — Ergebnis waere ungueltiges YAML ({exc}). config.yaml unveraendert.")
        return 1
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(txt)
    print(f"✅ config.yaml: {aktion}.")
    print(f"   Absender: {name}, {strasse}, {plz} {ort}")
    print(f"   Steuernummer: {steuernummer or '(noch leer — spaeter nachtragen)'}")
    print("   Pruefen:  python run.py check")
    return 0


def _config_setze_ebay_refresh(token: str) -> bool:
    """Schreibt den Refresh-Token direkt in config.yaml (formaterhaltend)."""
    import re
    path = "config.yaml"
    if not os.path.exists(path):
        return False
    with open(path, "r", encoding="utf-8") as fh:
        txt = fh.read()
    neu, n = re.subn(r"(?m)^(\s*refresh_token:\s*).*$",
                     lambda m: m.group(1) + '"' + token + '"', txt)
    if n:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(neu)
    return n > 0


def _signing_key_pfad(config: dict) -> str:
    return config.get("pfade", {}).get("ebay_signing_key", "data/ebay_signing_key.json")


def cmd_ebay_signkey(config: dict) -> int:
    """Erzeugt EINMALIG den Ed25519-Signaturschluessel fuer die Finances-API.

    eBay gibt den Private Key nur jetzt heraus; er wird gitignored unter
    data/ebay_signing_key.json gespeichert. Danach kann `ebay-finances` die
    echten Gebuehren signiert abrufen.
    """
    import json
    from src.integrations import EbayKeyManagement
    access_token, e = _ebay_access_token(config)
    if not access_token:
        print("Kein eBay-Token. Zuerst `ebay-auth` + `ebay-token` ausfuehren.")
        return 2
    pfad = _signing_key_pfad(config)
    if os.path.exists(pfad):
        bestand = _lade_json(pfad) or {}
        print(f"Es existiert bereits ein Signaturschluessel ({bestand.get('signing_key_id', '?')}).")
        print(f"Zum Neu-Erstellen die Datei loeschen: {pfad}")
        return 0
    try:
        km = EbayKeyManagement(access_token=access_token,
                               environment=e.get("environment", "production"))
        key = km.create_signing_key("ED25519")
    except Exception as exc:  # noqa: BLE001
        print(f"Schlusselerstellung fehlgeschlagen: {exc}")
        return 1
    if not key.private_key or not key.jwe:
        print("eBay hat keinen Private Key/JWE geliefert — Antwort unvollstaendig.")
        return 1
    daten = {
        "signing_key_id": key.signing_key_id, "jwe": key.jwe,
        "private_key": key.private_key, "public_key": key.public_key,
        "expiration_time": key.expiration_time, "cipher": key.cipher,
    }
    os.makedirs(os.path.dirname(pfad) or ".", exist_ok=True)
    with open(pfad, "w", encoding="utf-8") as fh:
        json.dump(daten, fh, ensure_ascii=False, indent=2)
    print(f"\n✅ Signaturschluessel erstellt und gespeichert -> {pfad} (gitignored).")
    print(f"   Key-ID: {key.signing_key_id}")
    if key.expiration_time:
        from datetime import datetime, timezone
        ablauf = datetime.fromtimestamp(key.expiration_time, tz=timezone.utc).date()
        print(f"   Gueltig bis: {ablauf}")
    print("   Jetzt echte Gebuehren ziehen:  python run.py ebay-finances")
    return 0


def _ebay_signing_context(config: dict):
    """Baut den SigningContext aus dem gespeicherten Schluessel (oder None)."""
    import time
    from src.integrations import SigningContext, ed25519
    daten = _lade_json(_signing_key_pfad(config))
    if not daten or not daten.get("jwe") or not daten.get("private_key"):
        return None
    seed = ed25519.seed_from_pkcs8(daten["private_key"])
    return SigningContext(jwe=daten["jwe"], seed=seed, clock=lambda: int(time.time()))


def cmd_ebay_finances(config: dict, tage: str = "") -> int:
    """Holt die ECHTEN eBay-Gebuehren signiert via Finances-API und schreibt sie
    nach data/ebay_fees.json (von `sync`/`run-all` bevorzugt verwendet)."""
    import json
    import time
    from datetime import date
    from src.integrations import EbayFinanceClient
    from src.util import parse_iso
    access_token, e = _ebay_access_token(config)
    if not access_token:
        print("Kein eBay-Token. Zuerst `ebay-auth` + `ebay-token` ausfuehren.")
        return 2
    signing = _ebay_signing_context(config)
    if signing is None:
        print("Kein Signaturschluessel. Zuerst `python run.py ebay-signkey` ausfuehren.")
        return 2
    start = _geschaeftsbeginn(config) or parse_iso("2026-01-01")
    ende = date.today()
    try:
        client = EbayFinanceClient(
            access_token=access_token,
            marketplace_id=e.get("marketplace_id", "EBAY_DE"),
            environment=e.get("environment", "production"), signing=signing)
        txs = client.get_all_transactions(start=start, end=ende)
    except Exception as exc:  # noqa: BLE001
        print(f"Finances-API fehlgeschlagen: {exc}\n"
              "Pruefe: Signaturschluessel gueltig, Scope sell.finances erteilt.")
        return 1
    s = EbayFinanceClient.fee_summary(txs)
    ergebnis = {
        "stand": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "zeitraum": {"von": start.isoformat(), "bis": ende.isoformat()},
        "fees_total": str(s["fees_total"]),
        "gebuehren": str(s.get("gebuehren", s["fees_total"])),
        "werbung": str(s.get("werbung", "0")),
        "sales_gross": str(s["sales_gross"]),
        "refunds_total": str(s["refunds_total"]), "n_sales": s["n_sales"],
        "transaktionen": len(txs),
    }
    pfad = config.get("pfade", {}).get("ebay_fees_export", "data/ebay_fees.json")
    os.makedirs(os.path.dirname(pfad) or ".", exist_ok=True)
    with open(pfad, "w", encoding="utf-8") as fh:
        json.dump(ergebnis, fh, ensure_ascii=False, indent=2)
    # Auszahlungen (PAYOUT) separat ablegen -> Konto-Abgleich (PayJoe-Rolle).
    payouts = [{"id": t.get("payoutId") or t.get("transactionId") or "",
                "date": (t.get("transactionDate") or "")[:10],
                "amount": (t.get("amount") or {}).get("value", "0")}
               for t in txs if (t.get("transactionType") or "").upper() == "PAYOUT"]
    payout_pfad = config.get("pfade", {}).get("ebay_payouts", "data/ebay_payouts.json")
    with open(payout_pfad, "w", encoding="utf-8") as fh:
        json.dump(payouts, fh, ensure_ascii=False, indent=2)
    print(f"Finances-API: {len(txs)} Transaktionen, {s['n_sales']} Verkaeufe "
          f"({start} – {ende}).")
    print(f"  Echte eBay-Gebuehren: {s['fees_total']} EUR "
          f"(davon Verkauf {s.get('gebuehren')} + Werbung {s.get('werbung')}) -> {pfad}")
    print(f"  eBay-Auszahlungen: {len(payouts)} -> {payout_pfad} (fuer Konto-Abgleich)")
    print(f"  (Brutto {s['sales_gross']} EUR, Refunds {s['refunds_total']} EUR)")
    print("  `python run.py sync` nutzt echte Gebuehren + Auszahlungen jetzt automatisch.")
    return 0


def cmd_ebay_sync(config: dict, tage: str = "30") -> int:
    from datetime import date, timedelta
    from src.integrations import EbayFinanceClient
    from src.imports import importiere_ebay_verkaeufe
    oauth, e = _ebay_oauth(config)
    if oauth is None:
        return 2
    try:
        if e.get("refresh_token"):
            # Bevorzugt: dauerhafter Refresh-Token -> frischer Access-Token.
            access_token = oauth.refresh(e["refresh_token"]).access_token
        elif e.get("access_token"):
            # Fallback: direkt hinterlegter User-Access-Token (kurzlebig, ~2 h!).
            print("Hinweis: nutze access_token direkt (laeuft ~2h ab). "
                  "Fuer Dauerbetrieb refresh_token via `ebay-auth`/`ebay-token` hinterlegen.")
            access_token = e["access_token"]
        else:
            print("Kein refresh_token/access_token in config.yaml — `ebay-auth` + `ebay-token` ausfuehren.")
            return 2
        client = EbayFinanceClient(access_token=access_token,
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
    # Zeilen fuer den `sync`-Lauf persistieren (data/ebay_rows.json + Payouts roh).
    import json
    export = config.get("pfade", {}).get("ebay_export", "data/ebay_rows.json")
    os.makedirs(os.path.dirname(export) or ".", exist_ok=True)
    with open(export, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2)
    payout_pfad = config.get("pfade", {}).get("ebay_payouts", "data/ebay_payouts.json")
    payouts_roh = [t for t in roh if (t.get("transactionType") or "").upper() == "PAYOUT"]
    with open(payout_pfad, "w", encoding="utf-8") as fh:
        json.dump(payouts_roh, fh, ensure_ascii=False, indent=2)
    print(f"eBay-Sync {start}..{ende}: {len(roh)} Transaktionen -> {len(sales)} Vorgaenge, "
          f"{len(payouts_roh)} Payouts.")
    print(f"  Verkaufszeilen: {export}; Payouts: {payout_pfad}")
    unklar = [r for r in rows if r.get("_review")]
    if unklar:
        print(f"  {len(unklar)} zur Pruefung markiert (unklarer Typ).")
    return 0


def _lexware_client(config: dict):
    from src.export.lexware import LexwareClient, RateLimiter
    lo = config.get("integrationen", {}).get("lexware_office", {})
    if not lo.get("api_key"):
        print("Kein Lexware-API-Key in config.yaml (integrationen.lexware_office.api_key).")
        return None, lo
    client = LexwareClient(
        api_key=lo["api_key"], base_url=lo.get("base_url", "https://api.lexoffice.io/v1"),
        finalize_belege=bool(lo.get("finalize_belege", False)),
        rate_limiter=RateLimiter(max_pro_sekunde=float(lo.get("rate_limit_rps", 2))),
    )
    return client, lo


def cmd_lexware_ping(config: dict) -> int:
    client, _ = _lexware_client(config)
    if client is None:
        return 2
    try:
        profil = client.ping()
    except Exception as exc:  # noqa: BLE001
        print(f"Lexware /profile fehlgeschlagen: {exc}")
        return 1
    print(f"Lexware OK: {profil.get('companyName', '?')} "
          f"(Mandant {profil.get('organizationId', '?')})")
    return 0


def _bank_transaktionen(config: dict, csv_path: str):
    from src.imports import importiere_lexware_bank
    mapping = config.get("integrationen", {}).get("bank", {}).get("csv_mapping") or None
    return importiere_lexware_bank(csv_path, mapping=mapping)


def cmd_bank_import(config: dict, csv_path: str = "") -> int:
    if not csv_path:
        print("Bitte CSV-Pfad angeben: python run.py bank-import <csv>")
        return 2
    try:
        txs = _bank_transaktionen(config, csv_path)
    except Exception as exc:  # noqa: BLE001
        print(f"Bankimport fehlgeschlagen: {exc}")
        return 1
    einnahmen = sum(1 for t in txs if t.betrag > 0)
    print(f"Bankimport: {len(txs)} Transaktionen ({einnahmen} Einnahmen, "
          f"{len(txs) - einnahmen} Ausgaben).")
    return 0


def _review_queue(config: dict):
    """Geteilte (persistente) Review-Queue — Pipeline und Bot teilen sich den Store."""
    from src.review import ReviewQueue
    return ReviewQueue(path=config.get("pfade", {}).get("review_store"))


def _ocr_belege(config: dict, belege_dir: str):
    """Verarbeitet alle Dateien in belege_dir durch die Beleg-Pipeline."""
    from src.ocr import BelegPipeline
    from src.storage import ReceiptStore
    store = ReceiptStore(config.get("pfade", {}).get("belegspeicher", "belege/"))
    queue = _review_queue(config)
    pipeline = BelegPipeline(store=store, review_queue=queue)
    receipts = []
    for name in sorted(os.listdir(belege_dir)):
        pfad = os.path.join(belege_dir, name)
        if not os.path.isfile(pfad):
            continue
        with open(pfad, "rb") as fh:
            content = fh.read()
        mime = "application/xml" if name.endswith(".xml") else "application/pdf"
        receipts.append(pipeline.verarbeite(content, mime=mime))
    return receipts, queue


def _lade_json(pfad: str):
    import json
    if not pfad or not os.path.exists(pfad):
        return None
    with open(pfad, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _geschaeftsbeginn(config: dict):
    from src.util import parse_iso
    return parse_iso(config.get("unternehmen", {}).get("geschaeftsbeginn"))


def _einkauf_ab(config: dict):
    """Frueheres Datum fuer Einkaufspreis-Sammlung (§25a-Ware aus Einlage).

    Faellt auf den Geschaeftsbeginn zurueck, wenn nicht gesetzt.
    """
    from src.util import parse_iso
    u = config.get("unternehmen", {})
    return parse_iso(u.get("einkauf_ab")) or _geschaeftsbeginn(config)


def cmd_ebay_kaeufe(config: dict, export_path: str = "") -> int:
    """Liest die eBay-Kaufhistorie (Export) -> data/einkaufspreise.json (ab Beginn)."""
    import json
    from src.integrations import normalisiere_kaeufe
    pfad = export_path or config.get("pfade", {}).get("ebay_kaeufe_export", "data/ebay_kaeufe.json")
    rows = _lade_json(pfad)
    if rows is None:
        print(f"Keine eBay-Kaufdaten gefunden ({pfad}). Bestellverlauf als JSON exportieren.")
        return 2
    ab = _einkauf_ab(config)              # frueher als der Geschaeftsbeginn (§25a-Einlage)
    preise, ignoriert = normalisiere_kaeufe(rows, ab=ab)
    ziel = config.get("pfade", {}).get("einkaufspreise", "data/einkaufspreise.json")
    os.makedirs(os.path.dirname(ziel) or ".", exist_ok=True)
    with open(ziel, "w", encoding="utf-8") as fh:
        json.dump({k: str(v) for k, v in preise.items()}, fh, ensure_ascii=False, indent=2)
    print(f"eBay-Kaeufe: {len(preise)} Einkaufspreise -> {ziel} "
          f"(ab {ab or '—'}; {len(ignoriert)} davor ignoriert).")
    return 0


def _ebay_wareneinkauf(config: dict, beginn):
    """Summe der eBay-Kaeufe ab Geschaeftsbeginn (Betriebsausgabe Wareneinkauf)."""
    from decimal import Decimal, InvalidOperation
    from src.util import parse_iso, ab_geschaeftsbeginn
    kaeufe = _lade_json(config.get("pfade", {}).get("ebay_kaeufe_export", "")) or []
    summe = Decimal("0")
    for k in kaeufe:
        d = parse_iso(k.get("date") or k.get("purchase_date"))
        if not ab_geschaeftsbeginn(d, beginn):
            continue
        roh = k.get("price") or k.get("total") or k.get("preis") or "0"
        try:
            summe += Decimal(str(roh).replace(",", "."))
        except InvalidOperation:
            continue
    return summe


def _ebay_verkaeufe(config: dict):
    """Laedt eBay-Verkaufszeilen aus dem konfigurierten Export (falls vorhanden)."""
    from src.imports import importiere_ebay_verkaeufe
    pfad = config.get("pfade", {}).get("ebay_export", "")
    rows = _lade_json(pfad)
    return importiere_ebay_verkaeufe(rows) if rows else []


def _rechnung_config(config: dict) -> dict:
    return config.get("rechnung", {}) or {}


def _absender(config: dict):
    from src.rechnung import Absender
    a = _rechnung_config(config).get("absender", {}) or {}
    # Fallback: Firmenname aus unternehmen.name, wenn absender.name leer.
    name = a.get("name") or config.get("unternehmen", {}).get("name", "")
    return Absender(
        name=name, strasse=a.get("strasse", ""), plz=str(a.get("plz", "")),
        ort=a.get("ort", ""), land=a.get("land", "DE"),
        steuernummer=str(a.get("steuernummer", "")), ust_id=a.get("ust_id", ""),
        email=a.get("email", ""), telefon=str(a.get("telefon", "")),
        iban=a.get("iban", ""), bic=a.get("bic", ""))


def _nummernkreis(config: dict):
    from src.rechnung import Nummernkreis
    rc = _rechnung_config(config)
    return Nummernkreis(
        pfad=rc.get("nummernkreis", "data/rechnungsnummern.json"),
        prefix=rc.get("nummer_prefix", ""),
        mit_jahr=bool(rc.get("nummer_mit_jahr", True)),
        start=int(rc.get("nummer_start", 1)))


def _rechnungs_register(config: dict):
    from src.rechnung import RechnungsRegister
    return RechnungsRegister(pfad=_rechnung_config(config).get(
        "register", "data/rechnungen_register.json"))


def cmd_rechnungen(config: dict) -> int:
    """Erzeugt fuer jeden eBay-Verkauf (ab Geschaeftsbeginn) eine Rechnung,
    rendert HTML+Text, archiviert sie und fuehrt ein idempotentes Register.
    Doppellaeufe erzeugen KEINE neuen Rechnungen (Register schuetzt davor)."""
    import json
    from src.rechnung import rechnung_aus_verkauf, render_html, render_text
    from src.util import ab_geschaeftsbeginn
    rc = _rechnung_config(config)
    if not rc.get("aktiv", True):
        print("Rechnungserstellung in config.yaml deaktiviert (rechnung.aktiv: false).")
        return 0
    if rc.get("modus", "alle") == "manuell":
        print("Modus 'manuell' — Rechnungen nur gezielt erzeugen (noch nicht implementiert: einzeln).")
        return 0
    absender = _absender(config)
    fehlt = absender.vollstaendig()
    if fehlt:
        print(f"⚠ Absenderdaten unvollstaendig ({', '.join(fehlt)}). Rechnungen werden "
              "erzeugt, sind aber erst mit vollstaendigem rechnung.absender rechtsgueltig.")
    beginn = _geschaeftsbeginn(config)
    sales = [s for s in _ebay_verkaeufe(config)
             if (not beginn or ab_geschaeftsbeginn(s.datum, beginn))]
    if not sales:
        print("Keine eBay-Verkaeufe gefunden. Zuerst `ebay-verkaeufe-api` ausfuehren.")
        return 0
    nk = _nummernkreis(config)
    reg = _rechnungs_register(config)
    verzeichnis = rc.get("verzeichnis", "belege/rechnungen/")
    os.makedirs(verzeichnis, exist_ok=True)
    ku = bool(config.get("steuer", {}).get("kleinunternehmer", True))
    hinweis = rc.get("kleinunternehmer_hinweis") or None
    neu = 0
    # Aeltere Verkaeufe zuerst -> Nummern in zeitlicher Reihenfolge.
    for s in sorted(sales, key=lambda x: (x.datum, str(x.id))):
        if reg.hat(str(s.id)):
            continue
        nummer = nk.naechste(s.datum.year)
        r = rechnung_aus_verkauf(s, nummer=nummer, absender=absender,
                                 kleinunternehmer=ku, hinweis=hinweis)
        basis = os.path.join(verzeichnis, nummer.replace("/", "-"))
        with open(basis + ".html", "w", encoding="utf-8") as fh:
            fh.write(render_html(r))
        with open(basis + ".txt", "w", encoding="utf-8") as fh:
            fh.write(render_text(r))
        with open(basis + ".json", "w", encoding="utf-8") as fh:
            json.dump(r.als_dict(), fh, ensure_ascii=False, indent=2)
        reg.merke(str(s.id), nummer, datei=basis + ".html", betrag=str(r.summe),
                  datum=r.datum.isoformat())
        neu += 1
    gesamt = len(reg.alle())
    print(f"Rechnungen: {neu} neu erzeugt -> {verzeichnis} "
          f"({gesamt} gesamt im Register).")
    if rc.get("lexware", {}).get("push"):
        print("Tipp: `python run.py rechnungen-push` uebertraegt offene Rechnungen nach Lexware.")
    return 0


def cmd_rechnungen_push(config: dict) -> int:
    """Uebertraegt lokal erzeugte, noch nicht uebermittelte Rechnungen nach Lexware
    Office (Entwurf; mit rechnung.lexware.finalize: true festgeschrieben)."""
    from src.integrations import LexwareInvoiceClient
    from src.rechnung import rechnung_aus_verkauf
    rc = _rechnung_config(config)
    lex = config.get("integrationen", {}).get("lexware_office", {})
    api_key = lex.get("api_key")
    if not api_key:
        print("Kein Lexware-API-Key in config.yaml (integrationen.lexware_office.api_key).")
        return 2
    reg = _rechnungs_register(config)
    offen = reg.offene_lexware()
    if not offen:
        print("Keine offenen Rechnungen fuer Lexware (alles uebertragen).")
        return 0
    sales_by_id = {str(s.id): s for s in _ebay_verkaeufe(config)}
    absender = _absender(config)
    ku = bool(config.get("steuer", {}).get("kleinunternehmer", True))
    hinweis = rc.get("kleinunternehmer_hinweis") or None
    finalize = bool(rc.get("lexware", {}).get("finalize", False))
    pdf_speichern = bool(rc.get("lexware", {}).get("pdf_speichern", True))
    verzeichnis = rc.get("verzeichnis", "belege/rechnungen/")
    client = LexwareInvoiceClient(api_key=api_key,
                                  base_url=lex.get("base_url", "https://api.lexware.io/v1"))
    erfolg, fehler = 0, 0
    for bid in offen:
        eintrag = reg.eintrag(bid) or {}
        nummer = eintrag.get("nummer", "")
        sale = sales_by_id.get(bid)
        if sale is None:
            print(f"  ⚠ Verkauf {bid} (Rechnung {nummer}) nicht mehr im Export — uebersprungen.")
            fehler += 1
            continue
        r = rechnung_aus_verkauf(sale, nummer=nummer, absender=absender,
                                 kleinunternehmer=ku, hinweis=hinweis)
        try:
            res = client.rechnung_anlegen(r, finalize=finalize)
            lex_id = res.get("id", "")
            extra = {"lexware_id": lex_id, "lexware_finalized": finalize}
            if pdf_speichern and lex_id:
                try:
                    pdf = client.pdf_laden(lex_id)
                    pdf_pfad = os.path.join(verzeichnis, nummer.replace("/", "-") + ".pdf")
                    with open(pdf_pfad, "wb") as fh:
                        fh.write(pdf)
                    extra["pdf"] = pdf_pfad
                except Exception as exc:  # noqa: BLE001 - PDF optional
                    print(f"  (PDF fuer {nummer} nicht geladen: {exc})")
            reg.merke(bid, nummer, **extra)
            erfolg += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ⚠ {nummer}: Lexware-Push fehlgeschlagen: {exc}")
            fehler += 1
    status = "festgeschrieben" if finalize else "als Entwurf"
    print(f"Lexware: {erfolg} Rechnungen {status} uebertragen, {fehler} Fehler.")
    return 0 if fehler == 0 else 1


def _euer_snapshot(config: dict):
    """Laedt den EÜR-Snapshot (von sync geschrieben) als leichtes Objekt."""
    from decimal import Decimal as D
    pfad = config.get("pfade", {}).get("euer_snapshot", "data/euer.json")
    daten = _lade_json(pfad)
    if not daten:
        return None

    class _E:
        einnahmen_gesamt = D(str(daten.get("einnahmen_gesamt", "0")))
        ausgaben_gesamt = D(str(daten.get("ausgaben_gesamt", "0")))
        gewinn = D(str(daten.get("gewinn", "0")))
        ausgaben_je_kategorie = {k: D(str(v))
                                 for k, v in (daten.get("ausgaben_je_kategorie") or {}).items()}
    return _E()


def cmd_bwa(config: dict) -> int:
    """BWA / Monatsabschluss aus dem letzten Sync (Umsatz, Rohertrag, Kosten,
    Gewinn, Kennzahlen, Monatsverlauf)."""
    from src.abschluss import erstelle_bwa, render_bwa_text, schreibe_bwa_csv
    from src.util import ab_geschaeftsbeginn
    euer = _euer_snapshot(config)
    if euer is None:
        print("Noch kein EÜR-Stand. Zuerst `python run.py sync` ausfuehren.")
        return 2
    beginn = _geschaeftsbeginn(config)
    sales = [s for s in _ebay_verkaeufe(config)
             if (not beginn or ab_geschaeftsbeginn(s.datum, beginn))]
    rahmen = config.get("kontierung", {}).get("rahmen", "skr03")
    bwa = erstelle_bwa(sales, euer, rahmen=rahmen, config=config.get("kontierung"))
    pfad = config.get("pfade", {}).get("bwa_csv", "data/bwa.csv")
    schreibe_bwa_csv(pfad, bwa)
    print(render_bwa_text(bwa))
    print(f"\n(CSV: {pfad})")
    return 0


def cmd_pruefung(config: dict) -> int:
    """Plausibilitaets- + Dublettenpruefung: Absender-IBAN/USt-IdNr, Rechnungs-
    Mathematik der erzeugten Rechnungen, Dubletten im Register."""
    from src.pruefung import (pruefe_iban, pruefe_ust_id, ist_dublette,
                              dubletten_schluessel, Schwere)
    befunde = []
    a = _absender(config)
    befunde.append(("Absender-IBAN", pruefe_iban(a.iban)))
    if a.ust_id:
        befunde.append(("Absender-USt-IdNr", pruefe_ust_id(a.ust_id)))
    # Dubletten im Rechnungsregister.
    reg = _rechnungs_register(config).alle()
    gesehen, dubletten = set(), 0
    for bid, e in reg.items():
        beleg = {"nummer": e.get("nummer"), "betrag": e.get("betrag"),
                 "datum": e.get("datum"), "kunde": bid}
        if ist_dublette(beleg, gesehen):
            dubletten += 1
        gesehen.add(dubletten_schluessel(beleg))
    print("🔎 Plausibilitaetspruefung")
    for label, b in befunde:
        zeichen = {"ok": "✓", "hinweis": "•", "fehler": "✗"}[b.schwere.value]
        print(f"  {zeichen} {label}: {b.nachricht}")
    print(f"  • Rechnungsregister: {len(reg)} Eintraege, {dubletten} Dubletten.")
    fehler = sum(1 for _, b in befunde if b.schwere == Schwere.FEHLER)
    print(f"\n{'⚠ ' + str(fehler) + ' Fehler' if fehler else '✓ keine formalen Fehler'}.")
    return 0


_FUNKTIONSUEBERSICHT = """SERO Agent — Funktionsumfang (gegen Master-Prompt):
  ✅ eBay-Verkaeufe/-Kaeufe ziehen (Trading-API)        -> ebay-verkaeufe-api / ebay-kaeufe-api
  ✅ Echte eBay-Gebuehren + Auszahlungen (signiert)     -> ebay-finances
  ✅ Rechnungen erstellen (rechtskonform, fortl. Nr.)   -> rechnungen
  ✅ Rechnungen nach Lexware (Entwurf/festschreiben)    -> rechnungen-push
  ✅ Differenzbesteuerung §25a / Kleinunternehmer §19   -> sync
  ✅ USt-VA-Kennzahlen (Kz 81/86/66/83) + EÜR           -> sync
  ✅ Automatische Kontierung SKR03/SKR04                -> (in sync/bwa)
  ✅ Plausibilitaet: IBAN/USt-IdNr/Mathematik/Dubletten -> pruefung
  ✅ BWA/Monatsabschluss (Rohertrag, Kennzahlen)        -> bwa
  ✅ Reconciliation Auszahlung<->Bank, Belege<->Bank    -> sync (+ Konto-CSV)
  ✅ Schwellen-Monitoring (§19, OSS 10k)                -> sync
  ✅ OCR-Beleg-Pipeline (Kategorie/Vorsteuer)           -> sync (+ Beleg-Inbox)
  ✅ DATEV-/CSV-Export, Audit-Log (revisionssicher)     -> export/, audit/
  ✅ Telegram-Steuerung + Freigaben + Duden             -> telegram
  ✅ Dauerbetrieb (Monitoring im Takt)                  -> serve
  🟡 PayPal-Anbindung   -> Client/Parser folgt (braucht PayPal-API-Keys)
  🟡 E-Mail-/Cloud-Ingest -> Gmail/Drive-Anbindung optional (Laufzeit-abhaengig)
  🟡 OCR-Backend        -> Pipeline da; echtes OCR braucht Provider (Textract o.ae.)
"""


def cmd_kann(config: dict) -> int:
    """Zeigt den Funktionsumfang (was automatisiert ist, was noch ansteht)."""
    print(_FUNKTIONSUEBERSICHT)
    return 0


def cmd_buchhaltung(config: dict) -> int:
    """DER EINE BEFEHL — komplette Buchhaltung ab Geschaeftsbeginn:
    eBay-Kaeufe+Verkaeufe ziehen, echte Gebuehren/Werbung/Auszahlungen holen,
    Rechnungen erzeugen + nach Lexware, alles gegen die Verkaeufe rechnen (EÜR),
    und eine saubere Schlussuebersicht ausgeben."""
    from decimal import Decimal as D
    ebay = config.get("integrationen", {}).get("ebay", {})
    lex = config.get("integrationen", {}).get("lexware_office", {})
    hat_token = bool(ebay.get("refresh_token") or ebay.get("access_token"))
    tage = str(config.get("betrieb", {}).get("ebay_sync_tage", 30))
    beginn = _geschaeftsbeginn(config)

    print("🧮 Komplette Buchhaltung wird erstellt …\n")
    if hat_token:
        _schritt("1/6 eBay-Kaeufe (Wareneinkauf)", lambda: cmd_ebay_kaeufe_api(config, tage))
        if os.path.exists(config.get("pfade", {}).get("ebay_kaeufe_export", "")):
            _schritt("    Einkaufspreise (§25a)", lambda: cmd_ebay_kaeufe(config))
        _schritt("2/6 eBay-Verkaeufe", lambda: cmd_ebay_verkaeufe_api(config, tage))
        if os.path.exists(_signing_key_pfad(config)):
            _schritt("3/6 Echte Gebuehren + Werbung + Auszahlungen",
                     lambda: cmd_ebay_finances(config))
        else:
            print("3/6 Gebuehren: kein Signaturschluessel — Schaetzung wird genutzt "
                  "(`python run.py ebay-signkey` fuer centgenaue Werte).")
    else:
        print("⚠ Kein eBay-Token — bitte `ebay-auth` + `ebay-token` zuerst.")

    _schritt("4/6 Rechnungen erzeugen (ab Geschaeftsbeginn)", lambda: cmd_rechnungen(config))
    if lex.get("api_key"):
        _schritt("5/6 Rechnungen -> Lexware (Entwurf)", lambda: cmd_rechnungen_push(config))
    else:
        print("5/6 Lexware-Push uebersprungen (kein API-Key in config.yaml).")
    _schritt("6/6 Gegenrechnung + EÜR (Verkaeufe − Gebuehren − Werbung − Wareneinkauf)",
             lambda: cmd_sync(config))

    # ---- Saubere Schlussuebersicht ----
    euer = _lade_json(config.get("pfade", {}).get("euer_snapshot", "data/euer.json")) or {}
    fees = _lade_json(config.get("pfade", {}).get("ebay_fees_export", "data/ebay_fees.json")) or {}
    payouts = _lade_json(config.get("pfade", {}).get("ebay_payouts", "data/ebay_payouts.json")) or []
    reg = _rechnungs_register(config)
    kat = euer.get("ausgaben_je_kategorie", {}) or {}

    def g(x):
        try:
            return D(str(x)).quantize(D("0.01"))
        except Exception:  # noqa: BLE001
            return D("0.00")

    payout_summe = sum((g(p.get("amount")) for p in payouts), D("0"))
    print("\n" + "═" * 52)
    print("  BUCHHALTUNG — SAUBERE ÜBERSICHT")
    print(f"  (ab {beginn or 'Geschaeftsbeginn'})")
    print("═" * 52)
    print(f"  Umsatz (Verkaeufe)        {g(euer.get('einnahmen_gesamt')):>12} EUR")
    print(f"  − Wareneinkauf            {g(kat.get('wareneinkauf')):>12} EUR")
    print(f"  − eBay-Verkaufsgebuehren  {g(kat.get('gebuehren')):>12} EUR")
    print(f"  − eBay-Werbung/Anzeigen   {g(kat.get('werbung')):>12} EUR")
    andere = sum((g(v) for k, v in kat.items()
                  if k not in ("wareneinkauf", "gebuehren", "werbung")), D("0"))
    if andere > 0:
        print(f"  − sonstige Ausgaben       {andere:>12} EUR")
    print("  " + "─" * 44)
    print(f"  = GEWINN                  {g(euer.get('gewinn')):>12} EUR")
    print("═" * 52)
    print(f"  Rechnungen gesamt: {len(reg.alle())}  ·  "
          f"noch nicht in Lexware: {len(reg.offene_lexware())}")
    if payouts:
        print(f"  eBay-Auszahlungen: {len(payouts)} · Summe {payout_summe} EUR")
    if fees.get("werbung"):
        print(f"  (Gebuehren echt aus eBay; Werbung separat: {fees.get('werbung')} EUR)")
    else:
        print("  (Tipp: `ebay-signkey` → centgenaue Gebuehren + Werbung getrennt)")
    if not lex.get("api_key"):
        print("  (Lexware-API-Key fehlt → Rechnungen noch nicht uebertragen)")
    a = _absender(config)
    if a.vollstaendig():
        print("  ⚠ Absender unvollstaendig (Steuernummer?) → `rechnung-setup`")
    print("═" * 52)
    return 0


def cmd_sync(config: dict, belege_dir: str = "", csv_path: str = "") -> int:
    from decimal import Decimal
    from src.reconciliation import Reconciler, MatchStatus
    from src.export import schreibe_buchungsjournal, schreibe_differenz_journal
    from src.tax import ustva_vorbereitung, journalisiere_verkaeufe
    from src.util import ab_geschaeftsbeginn
    ku = bool(config.get("steuer", {}).get("kleinunternehmer", True))
    # Pfade aus der Konfiguration uebernehmen, fehlende Quellen tolerieren:
    # so rechnet sync auch nur mit eBay-Daten (ohne Belege/Konto-CSV).
    belege_dir = belege_dir or config.get("pfade", {}).get("belege_inbox", "")
    csv_path = csv_path or config.get("pfade", {}).get("bank_csv", "")
    try:
        from src.imports import lese_ausgaben_csv
        queue = _review_queue(config)
        receipts = []
        if belege_dir and os.path.isdir(belege_dir):
            receipts, queue = _ocr_belege(config, belege_dir)
        # Echte Rechnungen aus der Ausgaben-CSV (Versand, Material, ...).
        receipts += lese_ausgaben_csv(config.get("pfade", {}).get("ausgaben_csv", ""))
        txs = []
        if csv_path and os.path.exists(csv_path):
            txs = _bank_transaktionen(config, csv_path)
        sales = _ebay_verkaeufe(config)
    except Exception as exc:  # noqa: BLE001
        print(f"Sync fehlgeschlagen: {exc}")
        return 1

    # Geschaeftsbeginn-Cutoff: alles vor der Gruendung gehoert in die private Sphaere.
    beginn = _geschaeftsbeginn(config)
    if beginn is not None:
        n_r, n_t, n_s = len(receipts), len(txs), len(sales)
        receipts = [r for r in receipts if ab_geschaeftsbeginn(r.datum, beginn)]
        txs = [t for t in txs if ab_geschaeftsbeginn(t.datum, beginn)]
        sales = [s for s in sales if ab_geschaeftsbeginn(s.datum, beginn)]
        vor = (n_r - len(receipts)) + (n_t - len(txs)) + (n_s - len(sales))
        if vor:
            print(f"Geschaeftsbeginn {beginn}: {vor} Vorgaenge vor Gruendung ignoriert.")

    os.makedirs("data", exist_ok=True)
    ergebnisse = Reconciler().reconcile(txs, receipts)
    n = schreibe_buchungsjournal("data/buchungsjournal.csv", ergebnisse)
    offen = sum(1 for r in ergebnisse if r.status == MatchStatus.REVIEW_REQUIRED)
    unmatched = sum(1 for r in ergebnisse if r.status == MatchStatus.UNMATCHED)
    print(f"Sync: {len(receipts)} Belege, {len(txs)} Banktransaktionen, {len(sales)} eBay-Verkaeufe.")
    print(f"  Beleg-Reconciliation -> {n} Zeilen (data/buchungsjournal.csv); "
          f"{offen} Review, {unmatched} ohne Beleg.")

    # Payout-Reconciliation: eBay-Auszahlungen <-> Bank-Eingaenge.
    from src.reconciliation import PayoutReconciler, PayoutStatus, extrahiere_payouts
    from src.export import schreibe_payout_journal
    payouts_roh = _lade_json(config.get("pfade", {}).get("ebay_payouts", "")) or []
    payouts = extrahiere_payouts(payouts_roh)
    if payouts:
        pmatches = PayoutReconciler().reconcile(payouts, txs)
        schreibe_payout_journal("data/payout_journal.csv", pmatches)
        p_ok = sum(1 for m in pmatches if m.status == PayoutStatus.MATCHED)
        p_diff = [m for m in pmatches if m.status == PayoutStatus.DIFFERENZ]
        p_un = sum(1 for m in pmatches if m.status == PayoutStatus.UNMATCHED)
        print(f"  Payout-Reconciliation -> {len(payouts)} Payouts: "
              f"{p_ok} ok, {len(p_diff)} Differenz, {p_un} ohne Bank-Eingang "
              f"(data/payout_journal.csv).")
        for m in p_diff:
            queue.add(f"Payout {m.payout_id}: Bank-Differenz {m.differenz} EUR", bezug=m.payout_id)

    # Verkaufs-Journal: § 25a-Margen + USt je Satz.
    einkaufspreise_raw = _lade_json(config.get("pfade", {}).get("einkaufspreise", "")) or {}
    einkaufspreise = {k: Decimal(str(v)) for k, v in einkaufspreise_raw.items()}
    journal = journalisiere_verkaeufe(sales, einkaufspreise)
    d = schreibe_differenz_journal("data/differenz_journal.csv", journal.differenz_eintraege)
    print(f"  § 25a-Journal -> {d} Margen-Eintraege (data/differenz_journal.csv); "
          f"USt aus Marge {journal.differenz_ust} EUR.")
    # § 25a betrifft nur die USt — fuer Kleinunternehmer (§19) irrelevant, daher
    # KEINE Review-Flut wegen fehlender Einkaufsbelege.
    if journal.review_ids and not ku:
        for sid in journal.review_ids:
            queue.add("Differenzbesteuerung mit unklarem Einkaufsbeleg", bezug=sid)
        print(f"  {len(journal.review_ids)} § 25a-Verkaeufe ohne Einkaufspreis -> Review.")
    if journal.deemed_supplier_ust > 0:
        print(f"  Deemed Supplier: {journal.deemed_supplier_ust} EUR USt bereits von eBay abgefuehrt.")

    # Schwellen-Monitoring (§ 19 laufend + OSS 10k; § 25a-Ware ist ausgenommen).
    from src.tax import SchwellenMonitor
    sch = config.get("schwellen", {})
    mon = SchwellenMonitor(
        ku_vorjahr_grenze=Decimal(str(sch.get("kleinunternehmer_vorjahr_eur", 25000))),
        ku_laufend_grenze=Decimal(str(sch.get("kleinunternehmer_laufend_eur", 100000))),
        oss_grenze=Decimal(str(sch.get("oss_fernverkauf_eur", 10000))),
        warnung_ab_prozent=Decimal(str(sch.get("warnung_ab_prozent", 80))),
    )
    ku_status = mon.kleinunternehmer_laufend(journal.umsatz_brutto)
    oss_status = mon.oss_fernverkauf(journal.oss_netto_eu_b2c)
    for st in (ku_status, oss_status):
        flag = "UEBERSCHRITTEN" if st.ueberschritten else ("WARNUNG" if st.warnung else "ok")
        print(f"  Schwelle {st.name}: {st.aktuell}/{st.grenze} EUR = {st.prozent}% [{flag}]")
        if st.warnung or st.ueberschritten:
            queue.add(f"Annaeherung/Ueberschreitung Schwelle {st.name}", bezug="schwellen")

    print(f"  Review-Queue: {len(queue.offen())} offen.")
    report = ustva_vorbereitung(
        "laufend", kleinunternehmer=ku,
        umsatzsteuer_je_satz=journal.regel_ust_je_satz, differenz_ust=journal.differenz_ust)
    if ku:
        print(f"  USt-VA: {report.hinweise[0]}")
    else:
        print(f"  USt-VA (Entwurf): Zahllast {report.zahllast} EUR.")

    # USt-VA-Kennzahlen-Entwurf (Kz 81/86/66/83) als CSV.
    from src.tax import ustva_kennzahlen, schreibe_ustva_csv, euer_uebersicht, schreibe_euer_csv
    netto_19 = journal.regel_netto_je_satz.get("19", Decimal("0")) + journal.differenz_netto
    netto_7 = journal.regel_netto_je_satz.get("7", Decimal("0"))
    kz = ustva_kennzahlen("laufend", kleinunternehmer=ku, netto_19=netto_19,
                          netto_7=netto_7, vorsteuer=Decimal("0"))
    schreibe_ustva_csv("data/ustva_kennzahlen.csv", kz)
    if not ku:
        print(f"  USt-VA-Kz: 81={kz.kennzahlen['81']} 86={kz.kennzahlen['86']} "
              f"66={kz.kennzahlen['66']} 83={kz.kennzahlen['83']} (data/ustva_kennzahlen.csv).")

    # EÜR-Übersicht (Einnahmen/Ausgaben je Kategorie).
    euer = euer_uebersicht(sales, receipts, kleinunternehmer=ku, zeitraum="laufend",
                           gewst_freibetrag=Decimal(str(sch.get("gewerbesteuer_freibetrag_eur", 24500))))
    # eBay-Wareneinkauf (ab einkauf_ab, also inkl. Altbestand) als Warenkosten.
    wareneinkauf = _ebay_wareneinkauf(config, _einkauf_ab(config))
    if wareneinkauf > 0:
        euer.ausgaben_je_kategorie["wareneinkauf"] = (
            euer.ausgaben_je_kategorie.get("wareneinkauf", Decimal("0")) + wareneinkauf)
        euer.hinweise.append("Wareneinkauf enthaelt auch vor Gruendung gekaufte Ware "
                             "(Einlage) — Bewertung/Behandlung mit Steuerberater klaeren.")
    # eBay-Verkaufsgebuehren: ECHT aus der Finances-API (signiert) bevorzugen,
    # sonst Schaetzung (% vom Umsatz + fixe Gebuehr je Verkauf).
    costs = config.get("costs", {})
    fees_pfad = config.get("pfade", {}).get("ebay_fees_export", "data/ebay_fees.json")
    fees_real = _lade_json(fees_pfad) if os.path.exists(fees_pfad) else None
    werbung = Decimal("0")
    if fees_real and Decimal(str(fees_real.get("fees_total", "0"))) > 0:
        # Verkaufsgebuehren und Werbe-/Anzeigengebuehren SEPARAT buchen.
        gebuehren = Decimal(str(fees_real.get("gebuehren", fees_real["fees_total"]))).quantize(Decimal("0.01"))
        werbung = Decimal(str(fees_real.get("werbung", "0"))).quantize(Decimal("0.01"))
        euer.hinweise.append(f"eBay-Gebuehren ECHT aus Finances-API ({fees_real.get('n_sales', '?')} "
                             f"Verkaeufe): Verkauf {gebuehren} + Werbung {werbung} EUR "
                             f"(Stand {str(fees_real.get('stand', ''))[:10]}).")
    else:
        fee_pct = Decimal(str(costs.get("ebay_fee_percent", 0.13)))
        fee_fix = Decimal(str(costs.get("ebay_fixed_per_order", 0.35)))
        gebuehren = (euer.einnahmen_gesamt * fee_pct + len(sales) * fee_fix).quantize(Decimal("0.01"))
        euer.hinweise.append(f"eBay-Gebuehren geschaetzt ({fee_pct*100:.0f} % + {fee_fix}/Verkauf); "
                             "fuer centgenau + Werbung getrennt: `python run.py ebay-finances`.")
    if gebuehren > 0:
        euer.ausgaben_je_kategorie["gebuehren"] = (
            euer.ausgaben_je_kategorie.get("gebuehren", Decimal("0")) + gebuehren)
    if werbung > 0:
        euer.ausgaben_je_kategorie["werbung"] = (
            euer.ausgaben_je_kategorie.get("werbung", Decimal("0")) + werbung)
    # Gesamtsumme + Gewinn neu berechnen.
    euer.ausgaben_gesamt = sum(euer.ausgaben_je_kategorie.values(), Decimal("0"))
    euer.gewinn = euer.einnahmen_gesamt - euer.ausgaben_gesamt
    schreibe_euer_csv("data/euer_uebersicht.csv", euer)
    print(f"  EÜR: Einnahmen {euer.einnahmen_gesamt} - Ausgaben {euer.ausgaben_gesamt} "
          f"= Gewinn {euer.gewinn} EUR (data/euer_uebersicht.csv).")
    if euer.ueber_gewst_freibetrag:
        queue.add("Gewinn ueber Gewerbesteuer-Freibetrag (24.500 EUR)", bezug="gewst")

    # Dashboard-Snapshot fuer den Telegram-Bot (/report, /schwellen).
    import json
    snapshot = {
        "belege": len(receipts), "banktransaktionen": len(txs), "verkaeufe": len(sales),
        "differenz_ust": str(journal.differenz_ust),
        "ustva_zahllast": (None if ku else str(report.zahllast)),
        "euer_gewinn": str(euer.gewinn),
        "euer_einnahmen": str(euer.einnahmen_gesamt),
        "euer_ausgaben": str(euer.ausgaben_gesamt),
        "kleinunternehmer": ku,
        "review_offen": len(queue.offen()),
        "schwellen": {
            "ku_laufend": {"aktuell": str(ku_status.aktuell), "grenze": str(ku_status.grenze),
                           "prozent": str(ku_status.prozent), "warnung": ku_status.warnung,
                           "ueberschritten": ku_status.ueberschritten},
            "oss": {"aktuell": str(oss_status.aktuell), "grenze": str(oss_status.grenze),
                    "prozent": str(oss_status.prozent), "warnung": oss_status.warnung,
                    "ueberschritten": oss_status.ueberschritten},
        },
    }
    status_pfad = config.get("pfade", {}).get("status", "data/status.json")
    with open(status_pfad, "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh, ensure_ascii=False, indent=2)

    # Reicher EÜR-Snapshot (fuer BWA/Monatsabschluss).
    euer_snapshot = {
        "zeitraum": "laufend",
        "einnahmen_gesamt": str(euer.einnahmen_gesamt),
        "ausgaben_gesamt": str(euer.ausgaben_gesamt),
        "gewinn": str(euer.gewinn),
        "ausgaben_je_kategorie": {k: str(v) for k, v in euer.ausgaben_je_kategorie.items()},
    }
    euer_pfad = config.get("pfade", {}).get("euer_snapshot", "data/euer.json")
    with open(euer_pfad, "w", encoding="utf-8") as fh:
        json.dump(euer_snapshot, fh, ensure_ascii=False, indent=2)

    _benachrichtige(config, queue, snapshot)
    return 0


def _benachrichtige(config: dict, queue, snapshot: dict) -> None:
    """Proaktive Telegram-Meldung neuer Faelle/Schwellen (guarded, nie crashen)."""
    import json
    tg = config.get("interface", {}).get("telegram", {})
    if not (tg.get("token") and tg.get("allowed_user_ids")):
        return
    from src.interface import baue_meldungen, TelegramNotifier
    state_pfad = config.get("pfade", {}).get("notify_state", "data/notified.json")
    state = _lade_json(state_pfad) or {}
    texte, neuer_state = baue_meldungen(queue.offen(), snapshot, state)
    if texte:
        try:
            TelegramNotifier(tg["token"], list(tg["allowed_user_ids"])).sende(
                "📬 SERO-Agent\n\n" + "\n\n".join(texte))
        except Exception as exc:  # noqa: BLE001
            print(f"  (Benachrichtigung fehlgeschlagen: {exc})")
    os.makedirs(os.path.dirname(state_pfad) or ".", exist_ok=True)
    with open(state_pfad, "w", encoding="utf-8") as fh:
        json.dump(neuer_state, fh, ensure_ascii=False, indent=2)


def cmd_lexware_push(config: dict, belege_dir: str = "") -> int:
    from src.integrations import LexwareSync
    if not belege_dir:
        print("Bitte Belege-Verzeichnis angeben: python run.py lexware-push <dir>")
        return 2
    client, lo = _lexware_client(config)
    if client is None:
        return 2
    kategorie_map = {k: v for k, v in (lo.get("kategorie_map") or {}).items() if v}
    if not kategorie_map:
        print("WARNUNG: kategorie_map leer — keine Belege werden gepusht. "
              "Lexware-Kategorie-UUIDs in config.yaml eintragen.")
    try:
        receipts, queue = _ocr_belege(config, belege_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"Belegverarbeitung fehlgeschlagen: {exc}")
        return 1
    sync = LexwareSync(client=client, kategorie_map=kategorie_map, review_queue=queue)
    res = sync.push_belege(receipts)
    print(f"Lexware-Push: {len(res.erstellt)} Draft-Vouchers erstellt, "
          f"{len(res.uebersprungen)} uebersprungen, {len(res.fehler)} Fehler.")
    for beleg_id, grund in res.uebersprungen[:10]:
        print(f"  - {beleg_id}: {grund}")
    return 0 if not res.fehler else 1


def cmd_check(config: dict) -> int:
    """Setup-Diagnose: zeigt pro Bereich, was konfiguriert ist und was noch fehlt."""
    integ = config.get("integrationen", {})
    ebay = integ.get("ebay", {})
    lex = integ.get("lexware_office", {})
    tg = config.get("interface", {}).get("telegram", {})
    llm = integ.get("llm", {})
    pfade = config.get("pfade", {})
    steuer = config.get("steuer", {})
    kat = {k: v for k, v in (lex.get("kategorie_map") or {}).items() if v}

    def zeile(ok: bool, label: str, hinweis: str = "") -> str:
        mark = "✓" if ok else "✗"
        return f"  [{mark}] {label}" + (f" — {hinweis}" if (hinweis and not ok) else "")

    print("== Setup-Check ==\n")
    print("Stammdaten / Steuer:")
    u = config.get("unternehmen", {})
    print(zeile(bool(u.get("geschaeftsbeginn")),
               f"Geschaeftsbeginn: {u.get('geschaeftsbeginn', '—')} "
               f"(Einkaufspreise ab {u.get('einkauf_ab', u.get('geschaeftsbeginn', '—'))})"))
    print(zeile(True, f"Kleinunternehmer (§19): {steuer.get('kleinunternehmer')}"))
    print(zeile(bool(steuer.get("ust_id")), "USt-IdNr", "beim BZSt beantragen (eBay-EU Pflicht)"))

    print("\neBay (Verkaeufe + § 25a-Einkaufspreise):")
    print(zeile(bool(ebay.get("app_id") and ebay.get("cert_id")), "App-ID + Cert-ID"))
    if ebay.get("refresh_token"):
        print(zeile(True, "Refresh-Token (dauerhaft) — RuName nicht noetig"))
    elif ebay.get("access_token"):
        print(zeile(True, "Access-Token hinterlegt (⏳ ~2h — fuer Dauerbetrieb refresh_token holen)"))
    else:
        print(zeile(False, "Refresh-/Access-Token", "ebay-auth -> ebay-token <code> ausfuehren"))
    print(zeile(os.path.exists(pfade.get("ebay_kaeufe_export", "")), "Kaufhistorie-Export",
               f"nach {pfade.get('ebay_kaeufe_export', 'data/ebay_kaeufe.json')} exportieren"))
    sign_pfad = pfade.get("ebay_signing_key", "data/ebay_signing_key.json")
    print(zeile(os.path.exists(sign_pfad), "Finances-Signaturschluessel (echte Gebuehren)",
               "fuer centgenaue eBay-Gebuehren: `python run.py ebay-signkey`"))

    print("\nLexware Office (Konto + Buchung):")
    print(zeile(bool(lex.get("api_key")), "API-Key"))
    print(zeile(bool(kat), f"kategorie_map ({len(kat)} UUIDs)",
               "via `lexware-kategorien` holen + eintragen"))
    print(zeile(os.path.exists(pfade.get("bank_csv", "")), "Konto-CSV (Inbox)",
               f"Umsaetze nach {pfade.get('bank_csv', 'inbox/kontoumsaetze.csv')} exportieren"))
    print(zeile(os.path.isdir(pfade.get("belege_inbox", "")), "Beleg-Inbox",
               f"Ordner {pfade.get('belege_inbox', 'inbox/belege/')} anlegen"))

    print("\nRechnungen (Billbee-Ersatz):")
    absender = _absender(config)
    fehlt_abs = absender.vollstaendig()
    print(zeile(not fehlt_abs, "Absenderdaten (§14 UStG)",
               f"in config.yaml rechnung.absender ergaenzen: {', '.join(fehlt_abs)}"
               if fehlt_abs else ""))
    rcfg = config.get("rechnung", {}) or {}
    push_an = rcfg.get("lexware", {}).get("push")
    print(zeile(True, f"Rechnungs-Push nach Lexware: {'an' if push_an else 'aus (manuell)'}"
               + (" · festgeschrieben" if rcfg.get('lexware', {}).get('finalize') else " · Entwurf")))

    print("\nInterfaces:")
    print(zeile(bool(tg.get("token")), "Telegram-Token"))
    print(zeile(bool(tg.get("allowed_user_ids")), "Telegram allowed_user_ids",
               "Bot anschreiben -> nennt deine ID"))
    print(zeile(bool(llm.get("api_key")), "Claude-API-Key",
               "optional: gegroundete /duden-Antworten + bessere Klassifikation"))

    fehlt = []
    if not (ebay.get("refresh_token") or ebay.get("access_token")):
        fehlt.append("eBay Refresh-Token")
    if not kat: fehlt.append("Lexware kategorie_map")
    if not os.path.exists(pfade.get("bank_csv", "")): fehlt.append("Konto-CSV")
    if not tg.get("allowed_user_ids"): fehlt.append("Telegram User-ID")
    print("\n" + ("✓ Alles Noetige vorhanden — `run.py run-all` ist startklar."
                  if not fehlt else f"Noch offen: {', '.join(fehlt)}"))
    return 0


def cmd_lexware_kategorien(config: dict) -> int:
    """Listet die Lexware-Buchungskategorien (UUID + Name) fuer die kategorie_map."""
    client, _ = _lexware_client(config)
    if client is None:
        return 2
    try:
        data = client._request("GET", "/posting-categories")
    except Exception as exc:  # noqa: BLE001
        print(f"Abruf /posting-categories fehlgeschlagen: {exc}")
        return 1
    eintraege = data if isinstance(data, list) else data.get("content", [])
    print("Lexware-Buchungskategorien (UUID — Name [Typ]):\n")
    for k in eintraege:
        print(f"  {k.get('id')}  —  {k.get('name')} [{k.get('type', '?')}]")
    print("\nPassende UUIDs in config.yaml unter integrationen.lexware_office.kategorie_map eintragen.")
    return 0


def cmd_gewinn(config: dict, bank_csv: str = "") -> int:
    """Schnelle EÜR auf Kontobasis (Ist-Prinzip): Einnahmen/Ausgaben/Gewinn ab Gruendung."""
    from decimal import Decimal
    from datetime import date
    from src.util import ab_geschaeftsbeginn
    pfad = bank_csv or config.get("pfade", {}).get("bank_csv", "")
    try:
        txs = _bank_transaktionen(config, pfad)
    except Exception as exc:  # noqa: BLE001
        print(f"Keine Kontodaten ({pfad}): {exc}\n"
              "Lexware-Kontoumsaetze als CSV exportieren und Pfad angeben:\n"
              "  python run.py gewinn <bank_csv>")
        return 2
    beginn = _geschaeftsbeginn(config)
    txs = [t for t in txs if ab_geschaeftsbeginn(t.datum, beginn)]
    if not txs:
        print(f"Keine Buchungen ab Geschaeftsbeginn ({beginn}).")
        return 0
    einnahmen = sum((t.betrag for t in txs if t.betrag > 0), Decimal("0"))
    ausgaben = sum((-t.betrag for t in txs if t.betrag < 0), Decimal("0"))
    gewinn = einnahmen - ausgaben
    von = min(t.datum for t in txs)
    bis = max(t.datum for t in txs)
    fb = Decimal(str(config.get("schwellen", {}).get("gewerbesteuer_freibetrag_eur", 24500)))
    print(f"\n  Gewinn seit Geschaeftsbeginn {beginn or '—'}")
    print(f"  Zeitraum der Buchungen: {von} .. {bis}  ({len(txs)} Kontobewegungen)\n")
    print(f"    Einnahmen:  {einnahmen:>12,.2f} EUR")
    print(f"    Ausgaben:   {ausgaben:>12,.2f} EUR")
    print(f"    ─────────────────────────────")
    print(f"    Gewinn:     {gewinn:>12,.2f} EUR\n")
    print("  (Ist-Prinzip / Kontobasis — schnelle Uebersicht; die detaillierte")
    print("   EÜR nach Kategorien liefert `sync` in data/euer_uebersicht.csv.)")
    if gewinn > fb:
        print(f"\n  Hinweis: Gewinn ueber Gewerbesteuer-Freibetrag ({fb} EUR).")
    return 0


def _ebay_access_token(config: dict):
    """Frischen eBay-Access-Token holen (Refresh bevorzugt, sonst direkt hinterlegt)."""
    from src.integrations import EbayOAuth
    e = config.get("integrationen", {}).get("ebay", {})
    if e.get("refresh_token") and e.get("app_id") and e.get("cert_id"):
        try:
            oauth = EbayOAuth(app_id=e["app_id"], cert_id=e["cert_id"],
                              environment=e.get("environment", "production"))
            return oauth.refresh(e["refresh_token"]).access_token, e
        except Exception as exc:  # noqa: BLE001
            print(f"Token-Refresh fehlgeschlagen: {exc}")
    return e.get("access_token"), e


def cmd_ebay_verkaeufe_api(config: dict, tage: str = "90") -> int:
    """Holt die eBay-Verkaeufe der letzten ~90 Tage via Trading-API (ohne Signatur)
    und schreibt sie nach data/ebay_rows.json (fuer sync)."""
    import json
    from src.integrations import EbayTradingClient
    access_token, e = _ebay_access_token(config)
    if not access_token:
        print("Kein eBay-Token. Zuerst `ebay-auth` + `ebay-token` ausfuehren.")
        return 2
    try:
        client = EbayTradingClient(access_token=access_token,
                                   environment=e.get("environment", "production"),
                                   site_id=("77" if e.get("marketplace_id", "EBAY_DE") == "EBAY_DE" else "0"))
        rows = client.get_seller_sales(tage=int(tage),
                                       default_tax_scheme=e.get("default_tax_scheme", "differenz"))
    except Exception as exc:  # noqa: BLE001
        print(f"Trading-API GetOrders (Verkaeufe) fehlgeschlagen: {exc}")
        return 1
    pfad = config.get("pfade", {}).get("ebay_export", "data/ebay_rows.json")
    os.makedirs(os.path.dirname(pfad) or ".", exist_ok=True)
    with open(pfad, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2)
    print(f"Trading-API: {len(rows)} Verkaufspositionen (letzte {min(int(tage), 90)} Tage) -> {pfad}.")
    return 0


def cmd_ebay_kaeufe_api(config: dict, tage: str = "90") -> int:
    """Holt die eBay-Kaeufe der letzten ~90 Tage live (Trading-API) und merged sie
    in data/ebay_kaeufe.json. Aeltere Kaeufe (Altbestand) brauchen den Website-Export."""
    import json
    from src.integrations import EbayOAuth, EbayTradingClient
    e = config.get("integrationen", {}).get("ebay", {})
    # Access-Token besorgen (Refresh bevorzugt, sonst direkt hinterlegt).
    access_token = None
    if e.get("refresh_token") and e.get("app_id") and e.get("cert_id"):
        try:
            oauth = EbayOAuth(app_id=e["app_id"], cert_id=e["cert_id"],
                              environment=e.get("environment", "production"))
            access_token = oauth.refresh(e["refresh_token"]).access_token
        except Exception as exc:  # noqa: BLE001
            print(f"Token-Refresh fehlgeschlagen: {exc}")
    if access_token is None:
        access_token = e.get("access_token")
    if not access_token:
        print("Kein eBay-Token. `ebay-auth`/`ebay-token` ausfuehren oder access_token setzen.")
        return 2
    try:
        client = EbayTradingClient(access_token=access_token,
                                   environment=e.get("environment", "production"),
                                   site_id=("77" if e.get("marketplace_id", "EBAY_DE") == "EBAY_DE" else "0"))
        neue = client.get_buyer_purchases(tage=int(tage))
    except Exception as exc:  # noqa: BLE001
        print(f"Trading-API GetOrders fehlgeschlagen: {exc}\n"
              "Hinweis: ggf. Consent mit passendem Scope erneuern; aeltere Kaeufe nur via Website-Export.")
        return 1
    # Mit vorhandenem Export mergen (Website-Export + API ergaenzen sich).
    pfad = config.get("pfade", {}).get("ebay_kaeufe_export", "data/ebay_kaeufe.json")
    bestand = _lade_json(pfad) or []
    bekannt = {(r.get("product_id"), r.get("date")) for r in bestand}
    ergaenzt = [r for r in neue if (r.get("product_id"), r.get("date")) not in bekannt]
    bestand.extend(ergaenzt)
    os.makedirs(os.path.dirname(pfad) or ".", exist_ok=True)
    with open(pfad, "w", encoding="utf-8") as fh:
        json.dump(bestand, fh, ensure_ascii=False, indent=2)
    print(f"Trading-API: {len(neue)} Kaeufe (letzte {min(int(tage), 90)} Tage), "
          f"{len(ergaenzt)} neu -> {pfad}.")
    print("Tipp: `python run.py ebay-kaeufe` erzeugt daraus die Einkaufspreise (ab einkauf_ab).")
    if int(tage) > 90:
        print("Hinweis: eBay liefert max. ~90 Tage; aeltere Kaeufe via Website-Bestellverlauf exportieren.")
    return 0


def _schritt(name: str, fn) -> bool:
    """Fuehrt einen Pipeline-Schritt robust aus (Fehler brechen den Lauf nicht ab)."""
    print(f"\n▶ {name}")
    try:
        fn()
        return True
    except Exception as exc:  # noqa: BLE001 - autonomer Lauf darf nicht crashen
        print(f"  ⚠ {name} uebersprungen/fehlgeschlagen: {exc}")
        return False


def cmd_run_all(config: dict) -> int:
    """Ein vollstaendiger Pipeline-Durchlauf — fuer Cron/Server. Jeder Schritt guarded."""
    from src.audit import AuditLog
    log = AuditLog(config["pfade"]["audit_log"])
    log.append("run_all.start", {})
    pfade = config.get("pfade", {})
    betrieb = config.get("betrieb", {})
    ebay = config.get("integrationen", {}).get("ebay", {})

    tage = str(betrieb.get("ebay_sync_tage", 30))
    hat_token = bool(ebay.get("refresh_token") or ebay.get("access_token"))

    # 1a) Neue eBay-Kaeufe live holen (Trading-API, keine Signatur noetig).
    if hat_token:
        _schritt("eBay-Kaeufe (Trading-API)", lambda: cmd_ebay_kaeufe_api(config, tage))

    # 1b) Kaufhistorie -> Einkaufspreise (nur wenn Export vorhanden).
    if os.path.exists(pfade.get("ebay_kaeufe_export", "")):
        _schritt("eBay-Kaeufe -> Einkaufspreise", lambda: cmd_ebay_kaeufe(config))

    # 2) eBay-Verkaeufe abrufen (Trading-API; Verkaufszeilen ohne Signatur).
    if hat_token:
        _schritt("eBay-Verkaeufe (Trading-API)",
                 lambda: cmd_ebay_verkaeufe_api(config, tage))

    # 2b) ECHTE Gebuehren signiert via Finances-API — nur wenn Signaturschluessel da.
    if hat_token and os.path.exists(_signing_key_pfad(config)):
        _schritt("eBay-Gebuehren (Finances-API, signiert)",
                 lambda: cmd_ebay_finances(config))

    # 2c) Rechnungen erzeugen (Billbee-Ersatz) + optional nach Lexware pushen.
    rc = config.get("rechnung", {}) or {}
    if rc.get("aktiv", True) and rc.get("modus", "alle") != "manuell":
        _schritt("Rechnungen erzeugen", lambda: cmd_rechnungen(config))
        if rc.get("lexware", {}).get("push") and \
                config.get("integrationen", {}).get("lexware_office", {}).get("api_key"):
            _schritt("Rechnungen -> Lexware", lambda: cmd_rechnungen_push(config))

    # 3) Auswertung — rechnet mit allem, was da ist (eBay-Verkaeufe genuegen;
    #    Belege/Konto-CSV werden einbezogen, wenn vorhanden).
    _schritt("Auswertung (§25a, USt-VA, EÜR, Schwellen, Reconciliation)",
             lambda: cmd_sync(config))

    log.append("run_all.ende", {})
    print("\n✓ run-all abgeschlossen.")
    return 0


def cmd_serve(config: dict, intervall_stunden: str = "") -> int:
    """Autonomer Dauerbetrieb: Telegram-Bot (Thread) + Pipeline im festen Takt."""
    import threading
    import time
    betrieb = config.get("betrieb", {})
    intervall = float(intervall_stunden or betrieb.get("pipeline_intervall_stunden", 6))

    tg = config.get("interface", {}).get("telegram", {})
    if tg.get("token") and tg.get("allowed_user_ids"):
        t = threading.Thread(target=cmd_telegram, args=(config,), daemon=True)
        t.start()
        print(f"Telegram-Bot gestartet (Thread). Pipeline-Takt: alle {intervall} h.")
    else:
        print(f"Telegram-Bot inaktiv (Token/Allowlist fehlt). Pipeline-Takt: alle {intervall} h.")

    while True:
        try:
            cmd_run_all(config)
        except KeyboardInterrupt:
            print("\nserve beendet.")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"Pipeline-Fehler: {exc}")
        try:
            time.sleep(max(intervall, 0.1) * 3600)
        except KeyboardInterrupt:
            print("\nserve beendet.")
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
    "ebay-kaeufe": cmd_ebay_kaeufe,
    "ebay-kaeufe-api": cmd_ebay_kaeufe_api,
    "ebay-verkaeufe-api": cmd_ebay_verkaeufe_api,
    "ebay-signkey": cmd_ebay_signkey,
    "ebay-finances": cmd_ebay_finances,
    "rechnung-setup": cmd_rechnung_setup,
    "rechnungen": cmd_rechnungen,
    "rechnungen-push": cmd_rechnungen_push,
    "buchhaltung": cmd_buchhaltung,
    "bwa": cmd_bwa,
    "pruefung": cmd_pruefung,
    "kann": cmd_kann,
    "lexware-ping": cmd_lexware_ping,
    "bank-import": cmd_bank_import,
    "sync": cmd_sync,
    "lexware-push": cmd_lexware_push,
    "run-all": cmd_run_all,
    "serve": cmd_serve,
    "check": cmd_check,
    "lexware-kategorien": cmd_lexware_kategorien,
    "gewinn": cmd_gewinn,
}


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "demo"
    if cmd in ("-h", "--help", "help") or cmd not in COMMANDS:
        print(__doc__)
        return 0 if cmd in ("-h", "--help", "help") else 2
    config = lade_config()
    # Beim Kopieren mit Kommentar (z. B. `... ebay-signkey  # erstellt ...`) gibt
    # eine interaktive zsh die Kommentarwoerter als Argumente weiter — alles ab dem
    # ersten mit `#` beginnenden Token verwerfen, damit das nicht crasht.
    extra = []
    for a in argv[2:]:
        if a.startswith("#"):
            break
        extra.append(a)
    if extra:
        return COMMANDS[cmd](config, *extra)
    return COMMANDS[cmd](config)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
