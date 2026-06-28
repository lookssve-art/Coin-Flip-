# Verfahrensdokumentation (GoBD)

- **Mandant:** SERO Handel (Einzelunternehmen)
- **Finanzamt / Bundesland:** Muenchen / Bayern
- **Rechtsform / Gewinnermittlung:** einzelunternehmen / EUER
- **Kleinunternehmer (§ 19 UStG):** ja
- **Software-Version (Agent):** 2.0.0
- **Stand:** 2026-06-28

> Automatisch generiert aus der aktiven Konfiguration. Bei jeder relevanten
> Prozessaenderung neu erzeugen; Versionen revisionssicher aufbewahren.

## 1. Zweck und Geltungsbereich

Diese Dokumentation beschreibt den EDV-gestuetzten Daten- und Belegfluss des
Buchhaltungs-Assistenz-Agenten. Der Agent assistiert und bereitet vor; alle
steuerlich verbindlichen Schritte (Festschreibung, USt-VA-Abgabe) erfordern
menschliche Freigabe (Human-in-the-Loop).

## 2. Belegeingang

- **Quellen:** eBay (Finances/Fulfillment), Webshop/PSP (Stripe, PayPal),
  Geschaeftskonto (Qonto/Finom/Aggregator), E-Mail-Eingang (IMAP),
  Papierbelege (Scan).
- **E-Rechnung:** XRechnung/ZUGFeRD werden am Eingang erkannt, validiert und im
  strukturierten Originalformat archiviert (Empfangspflicht seit 01.01.2025).
- **Papier:** Ersetzendes Scannen nur mit Qualitaetskontrolle; Originale erst
  nach protokollierter Pruefung vernichten.

## 3. Erfassung und Verarbeitung

- OCR (Cloud) bzw. strukturiertes Parsing (E-Rechnung) -> Klassifikation ->
  Vorsteuer-/Besteuerungslogik (Regel- vs. Differenzbesteuerung § 25a).
- Jede automatische Entscheidung wird als `Decision` (Grund, Regel, Quellen,
  Unsicherheitsgrad, Zeitstempel) festgehalten.
- Unsichere Faelle gehen in die Review-Queue (`REVIEW_REQUIRED`) und werden
  nicht ohne menschliche Freigabe gebucht.

## 4. Kontrollen (IKS)

- Idempotenz-Keys gegen Doppelbuchungen.
- Beleg <-> Bank-Abgleich; Betragsdifferenzen -> Review.
- Schwellen-Monitoring 25.000 / 100.000 / 10.000 EUR mit Fruehwarnung.
- eBay-USt-Reports werden gegen die eigene Buchung abgeglichen
  (Deemed-Supplier / Doppelversteuerung vermeiden).

## 5. Unveraenderbarkeit und Archivierung

- **Audit-Log:** append-only, SHA-256-hashverkettet (`audit/audit_log.jsonl`).
- **Belegspeicher:** inhaltsadressiert/WORM (`belege/`).
- Korrekturen ausschliesslich als nachvollziehbare Korrekturbuchung.

## 6. Aufbewahrungsfristen

- Buchungsbelege/Rechnungen: **8 Jahre**.
- Buecher/Jahresabschluss/Verfahrensdokumentation: **10 Jahre**.
- Geschaeftsbriefe (inkl. E-Mail): **6 Jahre**.
- Sicherheitsregel: im Zweifel 10 Jahre.

## 7. Auswertung / Export

- USt-VA- und EÜR-Vorbereitung, OSS-Quartalsaufstellung,
  Differenzbesteuerungs-Journal, DATEV-/Lexware-Export.
- Alle Ausgaben sind Entwuerfe; die Abgabe via ELSTER bleibt menschlicher Schritt.

## 8. Verantwortlichkeiten

- **Fachlich/steuerlich verantwortlich:** Inhaber (persoenlich nach dt. Recht).
- **Steuerberater:** Review der markierten Faelle, Jahresabschluss.
- **Agent:** Datenerfassung, Strukturierung, Plausibilitaet, Export-Vorbereitung.
