# SERO Accounting & Tax Operations Agent (DE / SME) — v2

Compliance-orientierter Buchhaltungs- und Steuer-**Assistenz**-Agent für ein kleines
deutsches Handelsunternehmen (eBay-/Webshop-Handel mit Sammelobjekten: TCG, Sealed,
Graded, Plush). Rechtsstand **2025/2026**, Bayern/München.

> **Ehrliche Grenze (bewusst oben):** Dieses System ersetzt **keinen Steuerberater**
> und **keine ELSTER-Abgabe**. Der Agent assistiert, strukturiert, prüft Plausibilität
> und bereitet Exporte vor — er entscheidet und signiert **nichts steuerlich
> Verbindliches** (Human-in-the-Loop). Ziel: 80–90 % weniger manuelle Arbeit.

Die vollständige Spezifikation steht in **[`docs/agent-spec-v2.md`](docs/agent-spec-v2.md)**.

## Warum v2

Ergänzt die vier Lücken, die in einer Betriebsprüfung über „anerkannt" vs.
„verworfen + Hinzuschätzung" entscheiden:

1. **E-Rechnung** (§ 14 UStG) — Empfangspflicht seit 01.01.2025, auch für Kleinunternehmer.
2. **GoBD / Verfahrensdokumentation** — Unveränderbarkeit + Pflicht-Selbstdokumentation.
3. **Differenzbesteuerung § 25a** — Margenbesteuerung für Sammlerware aus Privatankauf.
4. **OSS / Fernverkauf** — 10.000-€-Schwelle, mit § 25a-Ausnahme.

## Implementiertes Compliance-Fundament

| Bereich | Modul |
|---|---|
| Datenmodell (`Transaction`, `Invoice`, `Receipt`, `Product`, `Decision` …) | [`src/models.py`](src/models.py) |
| Append-only, **hash-verketteter** Audit-Log (GoBD-Unveränderbarkeit) | [`src/audit/audit_log.py`](src/audit/audit_log.py) |
| Revisionssicherer Belegspeicher (WORM, inhaltsadressiert) | [`src/storage/receipt_store.py`](src/storage/receipt_store.py) |
| **Differenzbesteuerung § 25a** (Einzel-/Gesamtdifferenz, USt-Herausrechnung) | [`src/tax/differenzbesteuerung.py`](src/tax/differenzbesteuerung.py) |
| Schwellen-Monitoring 25k / 100k / 10k mit Frühwarnung | [`src/tax/schwellen.py`](src/tax/schwellen.py) |
| **USt-VA-Vorbereitung** (nur Entwurf, kein ELSTER-Versand) | [`src/tax/ustva.py`](src/tax/ustva.py) |
| **E-Rechnungs-Empfang** (XRechnung/ZUGFeRD-Erkennung + Parsing) | [`src/einvoice/parser.py`](src/einvoice/parser.py) |
| Review-Queue + `REVIEW_REQUIRED`-Trigger (Human-in-the-Loop) | [`src/review/queue.py`](src/review/queue.py) |
| **Auto-Verfahrensdokumentation** (GoBD) | [`src/verfahrensdoku/generator.py`](src/verfahrensdoku/generator.py) |
| **Bank-/eBay-Import** (read-only, normalisierend, idempotent) | [`src/imports/`](src/imports/) |
| **Reconciliation-Grundlogik** (Bank ↔ Belege, Teilzahlung/Refund/Differenz) | [`src/reconciliation/engine.py`](src/reconciliation/engine.py) |
| **Lexware-Export** (Draft-Voucher, 2 req/s Rate-Limit-Backoff) | [`src/export/lexware.py`](src/export/lexware.py) |
| **DATEV-/CSV-Journal** (Buchungs- + §25a-Differenzjournal, offline) | [`src/export/datev_csv.py`](src/export/datev_csv.py) |
| **Telegram-Freigabe-/Review-Interface** (Human-in-the-Loop) | [`src/interface/telegram_bot.py`](src/interface/telegram_bot.py) |
| **OCR-/Beleg-Pipeline** (Extraktion → Klassifikation → WORM-Ablage → Review) | [`src/ocr/`](src/ocr/) |
| **Claude-Klassifikator** (Opus 4.8, optional, offizielles SDK) | [`src/ocr/classify.py`](src/ocr/classify.py) |

Damit sind **alle 7 MVP-Punkte** umgesetzt. Cloud-OCR (Textract/Document AI) ist als
injizierbarer Anbieter vorgesehen; ohne ihn gehen Bildbelege bewusst in die
Review-Queue, statt geraten zu werden.

## Telegram-Bot (Freigabe-Interface)

1. Trage Token und deine User-ID in `config.yaml` ein
   (`interface.telegram.token`, `interface.telegram.allowed_user_ids`).
2. Token prüfen: `python run.py telegram-check`
3. Bot starten: `python run.py telegram`

**User-ID herausfinden:** Bot starten (mit leerer Allowlist), dem Bot eine
Nachricht schicken — er antwortet mit deiner User-ID, die du dann in
`allowed_user_ids` einträgst und neu startest. Nur gelistete IDs dürfen Freigaben
erteilen (der Bot steuert Buchhaltungs-Freigaben).

**Befehle:** `/review` (offene Fälle), `/approve <ID>`, `/reject <ID>`, `/status`.
Jede Freigabe wird im Audit-Log protokolliert.

> Hinweis: Der Bot braucht ausgehenden Zugriff auf `api.telegram.org`. In manchen
> abgesicherten CI-/Cloud-Umgebungen ist dieser Host per Egress-Policy gesperrt —
> dort den Bot lokal bzw. auf dem Zielserver starten.

## eBay-Anbindung (gewerblich, read-only)

OAuth2-Consent-Flow für die Finances-/Fulfillment-APIs (lesen im Namen des Verkäufers).
App-ID, Cert-ID, Dev-ID und **RuName** (Redirect-URL-Name aus dem eBay Developer
Portal) gehören in `config.yaml` unter `integrationen.ebay`.

```bash
python run.py ebay-auth            # gibt die Consent-URL aus → im Browser bestätigen
python run.py ebay-token <code>    # Code aus der Redirect-URL → Refresh-Token erzeugen
#   → den ausgegebenen Refresh-Token in config.yaml eintragen
python run.py ebay-sync 30         # letzte 30 Tage Transaktionen abrufen + importieren
```

`ebay-sync` ruft die Finances-API ab, normalisiert Verkäufe/Gebühren/Refunds
([`src/integrations/ebay_finance.py`](src/integrations/ebay_finance.py)) und führt sie
durch den read-only Importer. Unklare Transaktionstypen werden markiert, nicht geraten.

| Modul | Inhalt |
|---|---|
| [`src/integrations/ebay_oauth.py`](src/integrations/ebay_oauth.py) | OAuth2: `consent_url` / `exchange_code` / `refresh` (Production) |
| [`src/integrations/ebay_finance.py`](src/integrations/ebay_finance.py) | Finances-API (read-only) → Importer-Zeilen |

> Hinweis: Die eBay-Endpunkte (`auth.ebay.com`, `api.ebay.com`, `apiz.ebay.com`)
> brauchen ausgehenden Zugriff — in dieser Sandbox per Egress-Policy gesperrt, daher
> lokal/auf dem Zielserver ausführen. Die Clients sind über injizierbares HTTP
> vollständig offline getestet.

## Lexware Office — Bank + Buchungs-Push (live)

Lexware Office ist hier zugleich das **Geschäftskonto**. Kontoumsätze werden als
**CSV-Export** importiert (die öffentliche API liefert keine Roh-Transaktionen);
Belege werden als **Draft-Vouchers** zurückgeschrieben (Festschreibung bleibt manuell).

```bash
python run.py lexware-ping              # API-Key prüfen (/profile)
python run.py bank-import umsaetze.csv  # Geschäftskonto-CSV importieren
python run.py sync ./belege umsaetze.csv  # Belege+Bank → Reconciliation → data/buchungsjournal.csv + USt-VA-Entwurf
python run.py lexware-push ./belege     # Belege als Draft-Vouchers nach Lexware (live)
```

`lexware-push` mappt jede interne Kategorie über `integrationen.lexware_office.kategorie_map`
(Lexware-Kategorie-UUIDs aus `/posting-categories`) auf einen Voucher; Belege ohne
Mapping, mit unsicherer Vorsteuer oder offener Review werden **übersprungen**, nicht gebucht.

### eBay-Verkäufe + § 25a im `sync`

`sync` zieht zusätzlich die eBay-Verkäufe (`pfade.ebay_export`, von `ebay-sync` befüllt)
und die Einkaufspreise (`pfade.einkaufspreise`, `{product_id: preis}`) und schreibt ein
**§ 25a-Differenzbesteuerungs-Journal** (`data/differenz_journal.csv`): Marge = Verkauf − Einkauf,
USt aus der Marge herausgerechnet. Regelbesteuerte Verkäufe fließen als USt je Satz in den
USt-VA-Entwurf. § 25a-Verkäufe **ohne** hinterlegten Einkaufspreis gehen in die Review
(kein Raten); von eBay als Deemed Supplier abgeführte USt wird **nicht** doppelt angesetzt.
Modul: [`src/tax/verkaeufe.py`](src/tax/verkaeufe.py).

### eBay-Käufe → Einkaufspreise (§ 25a)

Die Einkaufspreise ziehst du aus deiner eBay-Kaufhistorie (Bestellverlauf-Export, JSON):

```bash
python run.py ebay-kaeufe              # data/ebay_kaeufe.json → data/einkaufspreise.json
```

Bei mehreren Käufen desselben Artikels gewinnt der **letzte ab Gründung**; Käufe vor
dem Geschäftsbeginn (private Anschaffung) werden ausgeschlossen.
Modul: [`src/integrations/ebay_purchases.py`](src/integrations/ebay_purchases.py).

### Geschäftsbeginn-Cutoff

`unternehmen.geschaeftsbeginn` (z. B. `2026-06-01`) ist der harte Stichtag: Belege,
Banktransaktionen und Verkäufe **vor** der Gründung werden im `sync` ignoriert (saubere
Trennung privat/geschäftlich). Modul: [`src/util/datum.py`](src/util/datum.py).

### Schwellen-Monitoring im `sync`

`sync` überwacht automatisch die **§ 19-Grenze** (laufend 100.000 €) und die
**OSS-Fernverkauf-Schwelle** (10.000 € EU-B2C netto, **§ 25a-Ware ausgenommen**) und legt
bei Annäherung/Überschreitung einen Review-Fall an.

## Telegram-„Duden" (Wissensbasis A–Z)

Der Bot beantwortet Fragen zu allen relevanten Regeln per `/duden <frage>` —
E-Rechnung, Aufbewahrungsfristen, § 19, GoBD, § 25a, OSS, EÜR, Gewerbesteuer, USt-VA,
Einfuhrumsatzsteuer, Reverse-Charge, Vorsteuer, USt-Sätze, USt-IdNr, LUCID, DSGVO,
Deemed Supplier. Jeder Eintrag nennt die **Fundstelle** (z. B. `§ 25a UStG`).

- `/duden` (ohne Argument) listet alle Themen.
- `/duden <frage>`: Schlagwort-/Volltextsuche. Ist ein Claude-Key konfiguriert
  (`integrationen.llm.api_key`), formuliert Claude eine **gegroundete** Antwort
  ausschließlich aus den Treffern (keine Halluzination); sonst werden die KB-Einträge
  direkt ausgegeben.

Wissensbasis: [`src/wissen/duden.py`](src/wissen/duden.py) — *allgemeine Information,
keine Steuerberatung.*

| Modul | Inhalt |
|---|---|
| [`src/imports/lexware_bank.py`](src/imports/lexware_bank.py) | Geschäftskonto-CSV (tolerant) → idempotente Bank-Transaktionen |
| [`src/integrations/lexware_sync.py`](src/integrations/lexware_sync.py) | Receipts → Lexware Draft-Vouchers (Kategorie-Mapping, Review-Gate) |

> Hinweis: `api.lexoffice.io` braucht ausgehenden Zugriff (in dieser Sandbox gesperrt);
> lokal/auf dem Zielserver ausführen. Logik ist über injizierbares HTTP offline getestet.

## Schnellstart

```bash
pip install -r requirements.txt          # nur PyYAML als Laufzeit-Abhängigkeit
cp config.example.yaml config.yaml        # Mandanten-/Steuerparameter setzen

python run.py demo                         # End-to-End-Demo der Module
python run.py verfahrensdoku               # GoBD-Verfahrensdokumentation erzeugen
python run.py audit-verify                 # Hash-Kette des Audit-Logs prüfen

python -m unittest discover -s tests -v    # Tests (stdlib, ohne pytest)
```

`config.yaml`, `audit/` und `belege/` sind in `.gitignore` — sie enthalten
Mandanten-/Steuerparameter bzw. revisionssichere Originaldaten und gehören nicht
ins Repository.

## Konfiguration

Zentral ist der Parameter `steuer.kleinunternehmer` (§ 19 UStG):

- `true` → kein Vorsteuerabzug, keine USt-VA-Pflicht; der Agent warnt vor den
  Grenzen 25.000 € (Vorjahr) und 100.000 € (laufend).
- `false` → Regelbesteuerung mit Vorsteuerabzug (bindet 5 Jahre).

Alle weiteren Schwellen, Aufbewahrungsfristen und Integrations-Platzhalter stehen in
[`config.example.yaml`](config.example.yaml).

## Projektstruktur

```
run.py                       CLI-Einstieg (demo | verfahrensdoku | audit-verify)
config.example.yaml          Beispielkonfiguration
docs/agent-spec-v2.md        Vollständige Spezifikation v2
src/
  models.py                  Datenmodell (dataclasses, Decimal-Geldbeträge)
  audit/                     Append-only Hash-Chain-Log
  storage/                   WORM-Belegspeicher
  tax/                       § 25a, Schwellen, USt-VA
  einvoice/                  E-Rechnungs-Parser
  review/                    Review-Queue (Human-in-the-Loop)
  verfahrensdoku/            GoBD-Verfahrensdoku-Generator
tests/                       Unit-Tests (stdlib unittest)
```

## Rechtlicher Hinweis

Keine Steuer- oder Rechtsberatung. Verbindliche steuerliche Schritte (Festschreibung,
USt-VA-Abgabe via ELSTER, Jahresabschluss) erfordern **menschliche Freigabe** bzw.
einen **Steuerberater**. Siehe Spezifikation Abschnitt 0, 4, 10.
