"""Generator fuer die GoBD-Verfahrensdokumentation.

Die Verfahrensdokumentation ist Pflicht und beschreibt den gesamten Daten-/
Belegfluss (Eingang -> Erfassung -> Verarbeitung -> Archivierung -> Auswertung).
Sie muss fuer einen sachverstaendigen Dritten in angemessener Zeit nachvollziehbar
sein und so lange aufbewahrt werden wie die zugehoerigen Unterlagen (10 Jahre).

Dieses Modul erzeugt die Doku aus der aktiven Konfiguration heraus, damit sie nie
veraltet und stets den real eingesetzten Prozess abbildet.
"""

from __future__ import annotations

from datetime import date

from .. import __version__


def generiere_verfahrensdoku(config: dict, *, stand: date | None = None) -> str:
    """Erzeugt die Verfahrensdokumentation als Markdown aus der Konfiguration."""
    stand = stand or date.today()
    u = config.get("unternehmen", {})
    s = config.get("steuer", {})
    a = config.get("aufbewahrung", {})
    p = config.get("pfade", {})

    ku = "ja" if s.get("kleinunternehmer") else "nein"
    lines = [
        f"# Verfahrensdokumentation (GoBD)",
        "",
        f"- **Mandant:** {u.get('name', 'n/a')}",
        f"- **Finanzamt / Bundesland:** {u.get('finanzamt', 'n/a')} / {u.get('bundesland', 'n/a')}",
        f"- **Rechtsform / Gewinnermittlung:** {u.get('rechtsform', 'n/a')} / "
        f"{u.get('gewinnermittlung', 'n/a').upper()}",
        f"- **Kleinunternehmer (§ 19 UStG):** {ku}",
        f"- **Software-Version (Agent):** {__version__}",
        f"- **Stand:** {stand.isoformat()}",
        "",
        "> Automatisch generiert aus der aktiven Konfiguration. Bei jeder relevanten",
        "> Prozessaenderung neu erzeugen; Versionen revisionssicher aufbewahren.",
        "",
        "## 1. Zweck und Geltungsbereich",
        "",
        "Diese Dokumentation beschreibt den EDV-gestuetzten Daten- und Belegfluss des",
        "Buchhaltungs-Assistenz-Agenten. Der Agent assistiert und bereitet vor; alle",
        "steuerlich verbindlichen Schritte (Festschreibung, USt-VA-Abgabe) erfordern",
        "menschliche Freigabe (Human-in-the-Loop).",
        "",
        "## 2. Belegeingang",
        "",
        "- **Quellen:** eBay (Finances/Fulfillment), Webshop/PSP (Stripe, PayPal),",
        "  Geschaeftskonto (Qonto/Finom/Aggregator), E-Mail-Eingang (IMAP),",
        "  Papierbelege (Scan).",
        "- **E-Rechnung:** XRechnung/ZUGFeRD werden am Eingang erkannt, validiert und im",
        "  strukturierten Originalformat archiviert (Empfangspflicht seit 01.01.2025).",
        "- **Papier:** Ersetzendes Scannen nur mit Qualitaetskontrolle; Originale erst",
        "  nach protokollierter Pruefung vernichten.",
        "",
        "## 3. Erfassung und Verarbeitung",
        "",
        "- OCR (Cloud) bzw. strukturiertes Parsing (E-Rechnung) -> Klassifikation ->",
        "  Vorsteuer-/Besteuerungslogik (Regel- vs. Differenzbesteuerung § 25a).",
        "- Jede automatische Entscheidung wird als `Decision` (Grund, Regel, Quellen,",
        "  Unsicherheitsgrad, Zeitstempel) festgehalten.",
        "- Unsichere Faelle gehen in die Review-Queue (`REVIEW_REQUIRED`) und werden",
        "  nicht ohne menschliche Freigabe gebucht.",
        "",
        "## 4. Kontrollen (IKS)",
        "",
        "- Idempotenz-Keys gegen Doppelbuchungen.",
        "- Beleg <-> Bank-Abgleich; Betragsdifferenzen -> Review.",
        "- Schwellen-Monitoring 25.000 / 100.000 / 10.000 EUR mit Fruehwarnung.",
        "- eBay-USt-Reports werden gegen die eigene Buchung abgeglichen",
        "  (Deemed-Supplier / Doppelversteuerung vermeiden).",
        "",
        "## 5. Unveraenderbarkeit und Archivierung",
        "",
        f"- **Audit-Log:** append-only, SHA-256-hashverkettet (`{p.get('audit_log', 'audit/audit_log.jsonl')}`).",
        f"- **Belegspeicher:** inhaltsadressiert/WORM (`{p.get('belegspeicher', 'belege/')}`).",
        "- Korrekturen ausschliesslich als nachvollziehbare Korrekturbuchung.",
        "",
        "## 6. Aufbewahrungsfristen",
        "",
        f"- Buchungsbelege/Rechnungen: **{a.get('buchungsbelege_jahre', 8)} Jahre**.",
        f"- Buecher/Jahresabschluss/Verfahrensdokumentation: **{a.get('buecher_jahresabschluss_jahre', 10)} Jahre**.",
        f"- Geschaeftsbriefe (inkl. E-Mail): **{a.get('geschaeftsbriefe_jahre', 6)} Jahre**.",
        "- Sicherheitsregel: im Zweifel 10 Jahre.",
        "",
        "## 7. Auswertung / Export",
        "",
        "- USt-VA- und EÜR-Vorbereitung, OSS-Quartalsaufstellung,",
        "  Differenzbesteuerungs-Journal, DATEV-/Lexware-Export.",
        "- Alle Ausgaben sind Entwuerfe; die Abgabe via ELSTER bleibt menschlicher Schritt.",
        "",
        "## 8. Verantwortlichkeiten",
        "",
        "- **Fachlich/steuerlich verantwortlich:** Inhaber (persoenlich nach dt. Recht).",
        "- **Steuerberater:** Review der markierten Faelle, Jahresabschluss.",
        "- **Agent:** Datenerfassung, Strukturierung, Plausibilitaet, Export-Vorbereitung.",
        "",
    ]
    return "\n".join(lines)
