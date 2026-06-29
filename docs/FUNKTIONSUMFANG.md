# Funktionsumfang — Abgleich mit dem Master-Prompt

Stand: laufende Entwicklung. Legende: ✅ umgesetzt · 🟡 teilweise / braucht Zugang · 🔴 offen

| # | Master-Prompt-Punkt | Status | Wo / Befehl |
|---|---------------------|--------|-------------|
| 1 | Rechnungen/Belege automatisch erkennen | 🟡 | OCR-Beleg-Inbox (`inbox/belege/`) → `sync`; E-Mail/Cloud-Ingest offen |
| 2 | OCR (Nr., Datum, Netto/USt/Brutto …) | 🟡 | `src/ocr/` Pipeline vorhanden; echtes OCR-Backend (Textract o. ä.) muss angebunden werden |
| 3 | Rechnungen in Lexware hochladen + buchen | ✅ | Ausgangsrechnungen: `rechnungen` → `rechnungen-push`; Belege: Voucher-Push (`lexware-push`) |
| 4 | Dublettenprüfung | ✅ | `src/pruefung/` (Nr.+Betrag+Datum+Partner), Register idempotent; `pruefung` |
| 5 | Automatische Kontierung SKR03/SKR04 | ✅ | `src/kontierung/` (überschreibbar in `config.yaml`) |
| 6 | Umsatzsteuer (19/7/0 %, RC, IG, KU, §25a) | ✅ | `src/tax/` (USt-VA Kz 81/86/66/83, §25a, §19); `sync` |
| 7 | eBay (Bestellungen, Gebühren, Auszahlungen, Refunds) | ✅ | `ebay-verkaeufe-api`, `ebay-kaeufe-api`, `ebay-finances` (signiert) |
| 8 | PayPal (Zahlungen, Gebühren, Auszahlungen) | 🔴 | Client/Parser folgt — braucht PayPal-REST-Credentials |
| 9 | Bankkonto: Umsätze zuordnen | ✅ | Reconciliation `src/reconciliation/` (Konto-CSV aus Lexware → `inbox/`) |
| 10 | Offene Posten / überfällige Rechnungen | 🟡 | Register + Zahlungsabgleich; Mahnwesen offen |
| 11 | Plausibilität (IBAN, USt-IdNr, Mathematik …) | ✅ | `src/pruefung/` (IBAN mod-97, USt-IdNr-Format, netto+USt=brutto); `pruefung` |
| 12 | Fehlererkennung → keine Buchung, Freigabe verlangen | ✅ | Review-Queue + Telegram-Freigabe; nie stillschweigend gebucht |
| 13 | Monatsabschluss / BWA | ✅ | `bwa` (Umsatz, Rohertrag, Kosten, Gewinn, Quoten, Monatsverlauf) |
| 14 | Jahresabschluss vorbereiten (DATEV/CSV/PDF) | 🟡 | DATEV-/Buchungsjournal-CSV `src/export/`; Komplettpaket erweiterbar |
| 15 | Dokumentation / Audit-Log (revisionssicher) | ✅ | `audit/` Hash-verkettetes Append-only-Log; `audit-verify` |
| 16 | Sicherheit: nichts löschen, Backups, reversibel | ✅ | Lexware-Drafts (nicht festgeschrieben), gitignored Daten, append-only Audit |
| 17 | Dauerbetrieb / Monitoring | ✅ | `serve` (Pipeline-Takt + Telegram-Thread) |
| 18 | Kommunikation (Aktion/Ergebnis/Fehler/Risiken) | ✅ | Telegram-Bot + Konsolen-Ausgaben + Review-Begründungen |
| 19 | Ziel: maximale Automatisierung, Freigabe nur kritisch | ✅ | `run-all` orchestriert alles; Review nur bei Unsicherheit |

## Schnellüberblick im Terminal

```bash
python run.py kann          # diese Übersicht kompakt
python run.py check         # was ist konfiguriert / was fehlt
```

## Was noch echten Zugang braucht (ehrlich)

- **PayPal** (#8): offizielle PayPal-REST-API-Credentials (Client-ID/Secret).
- **OCR-Backend** (#2): ein OCR-Dienst (AWS Textract o. ä.) für Foto-/PDF-Belege.
- **E-Mail/Cloud** (#1): Gmail-/Drive-Anbindung, um Rechnungen automatisch einzusammeln.

Diese Punkte sind als nächste Bausteine vorbereitet; sie sind nur deshalb 🟡/🔴,
weil sie Zugangsdaten zu externen Diensten brauchen — nicht, weil die Logik fehlt.
