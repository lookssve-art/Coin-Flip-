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

Noch offen (spätere MVP-Stufen): Bank-/eBay-Import + Reconciliation, OCR-Pipeline,
Lexware-Export. Priorisiert wurde — wie in der Spezifikation gefordert — das
Compliance-Fundament **vor** den Komfortfeatures.

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
