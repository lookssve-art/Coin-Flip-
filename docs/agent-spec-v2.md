# AI Accounting & Tax Operations Agent (DE / SME) — v2

**Überarbeitete, rechtlich aktualisierte Fassung (Rechtsstand 2025/2026, Bayern/München)**
**Kontext: eBay-/Webshop-Handel mit Sammelobjekten (TCG, Sealed, Graded, Plush) + Sonstiges**

> Diese Fassung ergänzt v1 um die vier kritischen Lücken, die in jeder Betriebsprüfung über „anerkannt" vs. „verworfen + Hinzuschätzung" entscheiden:
> **(1) E-Rechnung, (2) GoBD/Verfahrensdokumentation, (3) Differenzbesteuerung §25a für Sammlerware, (4) OSS/Fernverkauf.**
> Plus: korrigierte Aufbewahrungsfristen, neue Kleinunternehmergrenzen, Human-in-the-Loop und ELSTER-Realität.

---

## 0. Vorab — die ehrliche Grenze (steht bewusst oben)

Dieses System **ersetzt keinen Steuerberater und keine ELSTER-Abgabe**. Du bleibst nach deutschem Recht **persönlich verantwortlich** für jede Erklärung. Der Agent **assistiert, strukturiert, ordnet zu, prüft Plausibilität und bereitet Exporte vor** — er **entscheidet und signiert nichts steuerlich Verbindliches**. Ziel ist 80–90 % weniger manuelle Arbeit, **nicht** 100 % autonome Steuer.

---

## 1. Rolle

Hochpräziser, compliance-orientierter Buchhaltungs- und Steuer-**Assistenz**-Agent für ein kleines deutsches Handelsunternehmen.

Hauptaufgaben:
- Vollständige, lückenlose Datenerfassung aller Geschäftsvorfälle
- Korrekte Zuordnung Einnahmen/Ausgaben inkl. Plattformgebühren, Versand, Refunds
- Beleg-/Rechnungsorganisation **GoBD-konform** (unveränderbar, nachvollziehbar, maschinell auswertbar)
- Vorbereitung steuerlich relevanter Daten für Export (Lexware Office / DATEV) und für USt-VA / EÜR
- Plausibilitäts- und Fehlerprüfung, Markierung aller unsicheren Fälle

Arbeitet wie: Buchhalter + Steuerassistent + Datenintegrations-Layer **mit zwingender menschlicher Freigabe an definierten Punkten.**

---

## 2. Rechtlicher Rahmen 2025/2026

### 2.1 E-Rechnung (§ 14 UStG, Wachstumschancengesetz)
- **Empfangspflicht seit 01.01.2025 — ausnahmslos**, auch für Kleinunternehmer. Der Agent **muss** EN-16931-konforme Formate (XRechnung = reines XML, ZUGFeRD/Factur-X = PDF/A-3 + XML) **empfangen, validieren, den strukturierten Datensatz auslesen und revisionssicher archivieren** können. Eine PDF ohne strukturierten Datensatz ist **keine** E-Rechnung, sondern „sonstige Rechnung".
- **Versandpflicht gestaffelt:** 2025–2026 Übergangsfrist (Papier/PDF mit Zustimmung des Empfängers erlaubt); ab 01.01.2027 Pflicht für Aussteller mit > 800.000 € Vorjahresumsatz; ab 01.01.2028 für **alle** im inländischen B2B.
- **Ausnahmen vom Versand:** B2C (Privatkunden), Kleinbetragsrechnungen ≤ 250 €, Fahrausweise. **Kleinunternehmer (§19) sind dauerhaft vom Ausstellen befreit** — dürfen aber freiwillig E-Rechnungen senden und **müssen empfangen**.
- **Archivierung:** E-Rechnung muss **im strukturierten Originalformat 8 Jahre elektronisch** aufbewahrt werden. Ausdruck reicht nicht.

> Praxis SERO: B2C-Endkunden (eBay) → kein E-Rechnungs-Versand nötig. **Eingangsrechnungen** (Lieferanten, Großhandel, Software, eBay-Gebührenbelege) kommen aber zunehmend als E-Rechnung → Empfang + strukturierte Verbuchung ist Pflichtmodul.

### 2.2 Aufbewahrungsfristen
- **8 Jahre:** Buchungsbelege & Rechnungen (Rechnungen, Quittungen, Kontoauszüge, Lieferscheine, Zahlungsbelege) — seit 01.01.2025 (BEG IV), für alle am 31.12.2024 noch laufenden Fristen.
- **10 Jahre:** Bücher, Aufzeichnungen, Inventare, Jahresabschlüsse, Eröffnungsbilanz, **Verfahrensdokumentation**.
- **6 Jahre:** empfangene/abgesandte Handels- & Geschäftsbriefe (auch E-Mails), Lohnkonten.
- Fristbeginn: Schluss des Kalenderjahres der letzten Bearbeitung/des Empfangs.
- **Sicherheitsregel des Agenten:** Im Zweifel und bei allem, was auch in Bilanz/GuV/Jahresabschluss einfließt → **10 Jahre** ansetzen. (Die Aug-2025-Rückausnahme auf 10 Jahre betrifft nur Banken/Versicherungen/Wertpapierinstitute — für SERO nicht relevant.)

### 2.3 Kleinunternehmerregelung (§ 19 UStG, reformiert ab 01.01.2025)
- **Vorjahresgrenze 25.000 € (netto)** UND **laufendes Jahr 100.000 €**. Beide Bedingungen müssen erfüllt sein.
- Die 100.000 € sind **keine Prognose mehr, sondern harte Grenze („Fallbeileffekt")**: der Umsatz, **mit dem** die Grenze überschritten wird, ist bereits voll regelbesteuert; frühere Umsätze des Jahres bleiben steuerfrei.
- Seit 2025 ist es eine **Steuerbefreiung** (vorher: Nichterhebung) → Prüfung erfolgt auf **Netto**umsätze.
- **Wichtig für SERO:** Als Kleinunternehmer **kein Vorsteuerabzug** (auch nicht auf Importe/Einfuhrumsatzsteuer). Wer viel einkauft/importiert und Vorsteuer ziehen will, **muss zur Regelbesteuerung optieren** (bindet 5 Jahre). → **KU-Status ist ein konfigurierbarer Parameter `kleinunternehmer: true/false`**, den der Agent kennen muss, und er muss aktiv warnen, bevor die 25k-/100k-Grenze gerissen wird.
- Auch Kleinunternehmer brauchen für eBay-EU-Verkäufe eine **USt-IdNr** (beim BZSt beantragen, bei eBay hinterlegen).

### 2.4 GoBD + Verfahrensdokumentation
- GoBD gelten **auch für Kleinunternehmer und EÜR-Rechner**, sobald Prozesse EDV-gestützt laufen.
- Kernanforderungen: **Nachvollziehbarkeit, Vollständigkeit, Richtigkeit, Zeitgerechtigkeit, Ordnung, Unveränderbarkeit, maschinelle Auswertbarkeit.**
- **Editierbare Word-/PDF-Dateien im Explorer sind GoBD-widrig** (keine Unveränderbarkeit) → Risiko, dass die gesamte Buchführung verworfen und geschätzt wird.
- **Ersetzendes Scannen** (Papier scannen + Original vernichten) ist nur mit dokumentiertem, protokolliertem Prozess zulässig: zeitnah, bildgleich, vollständig, mit Qualitätskontrolle und festgelegter Verantwortlichkeit.
- **Verfahrensdokumentation ist Pflicht** und beschreibt den gesamten Daten-/Belegfluss (Eingang → Erfassung → Verarbeitung → Archivierung → Auswertung). Sie muss für einen sachverständigen Dritten in angemessener Zeit nachvollziehbar sein und **so lange aufbewahrt werden wie die zugehörigen Unterlagen**.
- **→ Eigenes Agenten-Modul:** generiert und pflegt automatisch die Verfahrensdokumentation für die eigene Pipeline (welches System macht was, welche Regeln, welche Kontrollen, Versionierung der Änderungen).

### 2.5 OSS / Fernverkauf + Differenzbesteuerung
- **EU-weite Lieferschwelle 10.000 € netto** (Summe **aller** B2C-Fernverkäufe in **alle** EU-Länder zusammen). Darüber: Besteuerung im **Bestimmungsland** mit dortigem Satz; zentrale Meldung über **OSS** beim BZSt (quartalsweise) statt lokaler Registrierungen.
- **Ausnahme, die für SERO Gold wert ist:** Lieferungen von **Gebrauchtgegenständen, Sammlungsstücken, Kunst, Antiquitäten** unter **Differenzbesteuerung (§ 25a UStG)** fallen **nicht** unter die Fernverkaufsregelung → bleiben in **Deutschland** steuerpflichtig, **kein** OSS nötig. (Viele Pokémon-/OP-Karten aus privatem Ankauf erfüllen das.)
- **Differenzbesteuerung (§ 25a):** Besteuert wird nur die **Marge** (Verkauf − Einkauf), typisch bei Ankauf von Privatpersonen (ohne Vorsteuer). USt darf **nicht** offen ausgewiesen werden. Erfordert **artikelgenaue Einkaufspreis-Erfassung**; zwei Methoden: Einzeldifferenz oder Gesamtdifferenz (für Posten ≤ 750 €). → **Agent muss pro Artikel `besteuerung: regel | differenz` führen** und Einkaufsbeleg verknüpfen. Mischbestände sauber trennen.
- **eBay als „elektronische Schnittstelle":** eBay kann in bestimmten Konstellationen die USt selbst abführen / als deemed supplier auftreten. eBay verlangt bei Überschreiten der 10k-Schwelle die OSS-Bestätigung oder hinterlegte USt-IdNr, sonst Kontosperre. → Agent muss eBay-Steuerreports gegen die eigene Buchung abgleichen (Doppelversteuerung vermeiden).

### 2.6 Weitere relevante Punkte
- **EÜR** (Einnahmen-Überschuss-Rechnung) ist für dich als kleines Einzelunternehmen der Regelfall: **Ist-Prinzip / Zufluss-Abfluss** → der **Zahlungszeitpunkt** (Bank) bestimmt, in welchem Jahr Einnahme/Ausgabe gebucht wird. Anlage EÜR ist **elektronisch über ELSTER** abzugeben.
- **Gewerbesteuer:** Freibetrag **24.500 € Gewinn** für Einzelunternehmer/Personengesellschaften.
- **USt-Voranmeldung:** Rhythmus (monatlich/quartalsweise/jährlich) gibt das Finanzamt vor; in den ersten beiden Jahren der Regelbesteuerung oft monatlich. **Dauerfristverlängerung** möglich.
- **Wegfall der 150-€-Zollfreigrenze (2026):** Importe (z. B. AliExpress) → für nahezu jede Sendung können Zoll + Einfuhrumsatzsteuer anfallen. Agent muss Import-Belege + EUSt separat erfassen.
- **LUCID / Verpackungsregister (VerpackG):** Registrierung + Mengenmeldung Pflicht für Versandhändler — Agent erinnert/trackt, bucht aber nicht.
- **DSGVO:** Kundendaten (Namen, Adressen) sind personenbezogen → Speicherung, Zugriff, Löschkonzept dokumentieren.

---

## 3. Integrationen / Datenquellen

| Quelle | Anbindung | Realität / Caveat |
|---|---|---|
| **Lexware Office** | **Public API (REST, OAuth2/API-Key, kostenlos)** | Nur EUR; Steuersätze 0/5/7/16/19 %; **Rate-Limit 2 req/s** (HTTP 429) → Backoff/Queue; Belege werden per API **default als Draft** angelegt (`finalize`-Flag nötig); API-Key läuft ab (erneuern); Webhooks (`invoice.status.changed`, Kontakt-Events). Abschlagsrechnungen nicht via API. |
| **DATEV** | Export DATEV-Format (EXTF/CSV) | Falls Steuerberater auf DATEV sitzt: sauberes Buchungs-CSV erzeugen statt Live-API. |
| **Geschäftskonto** | **PSD2**: FinTS/EBICS **oder** Aggregator (FinAPI, Klarna Kosma/Tink, GoCardless Bank Account Data) | Direkter Bank-Zugriff oft nur lesend; SCA/Re-Auth alle 90 Tage. **Qonto/Finom** (deine Kandidaten) haben eigene REST-APIs → bevorzugen. |
| **eBay** | eBay APIs (Finances, Fulfillment, Transaction reports) + Trading API (Messaging) | Gebühren, Refunds, Versand, eBay-USt-Reports getrennt ziehen. |
| **Webshop / PSP** | Stripe, PayPal APIs | Auszahlungen ≠ Einzelumsätze → auf Transaktionsebene auflösen. |
| **Belege** | OCR (AWS Textract / Google Document AI / Tesseract) | Reine Tesseract-Qualität bei Thermobons schwach → Cloud-OCR + manuelle Korrektur-Queue. |
| **E-Mail-Eingang** | IMAP + XRechnung/ZUGFeRD-Parser | Strukturierten Datensatz auslesen, nicht nur PDF-Bild. |

---

## 4. Kernprinzipien (nicht verhandelbar)

1. **Compliance First** — ausschließlich geltendes deutsches Steuerrecht (EStG, UStG, AO, GoBD). Keine erfundenen Regeln. Unsicher → `REVIEW_REQUIRED (Steuerberater)`.
2. **Keine illegale Steuervermeidung** — legitime Optimierung (AfA, Betriebsausgaben, Vorsteuer korrekt) ja; Verschleierung, manipulierte Belege/Umsätze nein.
3. **Human-in-the-Loop** — der Agent bucht/schlägt vor; **finalisierende Schritte** (Beleg festschreiben, USt-VA absenden, Status „bezahlt") erfordern menschliche Freigabe gemäß Schwellen (s. 7).
4. **Keine Halluzination** — keine Annahme als Fakt; fehlende Daten werden **nicht erfunden**, sondern als Lücke markiert.
5. **Unveränderbarkeit** — jeder erfasste Beleg wird festgeschrieben; Änderungen nur als nachvollziehbare, protokollierte Korrekturbuchung (GoBD).

---

## 5. Funktionsmodule

### 5.1 Transaktions-Zuordnung
Eingehende Zahlung → Quelle erkennen (eBay/Webshop/Bank/manuell) → mit Beleg/Rechnung matchen oder Entwurf erzeugen → Betrag/Datum/**Gebühren getrennt** abgleichen → Plattformgebühren (eBay Fees) als eigene Ausgabe buchen.

### 5.2 Beleg-/OCR-Verarbeitung
PDF/Bild → OCR → klassifizieren (Wareneinkauf, Büro, Software, Versand, Werbung, …) → Vorsteuerabzug `ja/nein/unsicher` → strukturiert speichern (Datum, Händler, brutto/netto, USt-Satz/-Betrag, Zahlungsart). **Bei E-Rechnung: strukturierten Datensatz parsen, nicht OCR.**

### 5.3 Bankabgleich (Reconciliation)
Bank ↔ Belege; erkennt Teilzahlungen, Gebühren, Refunds, Chargebacks; markiert Unstimmigkeiten. Bei EÜR: **Zahlungsdatum = Buchungsjahr.**

### 5.4 eBay / Webshop + Differenzbesteuerung
Umsatz erkennen, Gebühren/Versand/Refunds spiegeln. **Pro Artikel** Besteuerungsart (`regel`/`differenz`) führen, Einkaufsbeleg verknüpfen, Marge berechnen. eBay-USt-Reports gegen eigene Buchung abgleichen (Deemed-Supplier-Fälle, OSS-Schwelle 10k tracken — **§25a-Ware aus der Schwellen-Berechnung ausnehmen**).

### 5.5 E-Rechnung (Empfang)
Format erkennen (XRechnung/ZUGFeRD), validieren (Formatfehler vs. Geschäftsregelfehler), strukturierte Felder extrahieren, verbuchen, **Original 8 J. archivieren.** Ungültiges Format → `REVIEW_REQUIRED`.

### 5.6 USt-Logik
Regelbesteuerung (0/7/19 %), Differenzbesteuerung (§25a), Reverse-Charge (B2B-EU mit gültiger USt-IdNr), Einfuhrumsatzsteuer, KU-Steuerbefreiung — je nach `kleinunternehmer`-Flag und Artikel-/Kundentyp. Schwellen-Monitoring 25k/100k/10k mit Frühwarnung.

### 5.7 Verfahrensdokumentation (Selbst-Doku)
Generiert/aktualisiert laufend die GoBD-Verfahrensdokumentation der eigenen Pipeline inkl. Rollen, Kontrollen, Versionierung.

---

## 6. Datenmodell

`Transaction`, `Invoice` (+ `eInvoiceFormat`, `structuredPayload`), `Receipt` (+ `ocrConfidence`, `archivedHash`), `Customer` (+ `vatId`, `country`, `isBusiness`), `PlatformSale` (eBay/Webshop), `Product` (+ `purchasePrice`, `taxScheme: regel|differenz`, `purchaseReceiptRef`), `ExpenseCategory`, `TaxRuleSnapshot`, **`Decision`** (Grund, Quellen, Regel, Unsicherheitsgrad, Zeitstempel), **`ReviewItem`**, **`ProcedureDoc`** (Verfahrensdokumentation-Version).

> Umsetzung siehe [`src/models.py`](../src/models.py).

---

## 7. „Single Source of Truth" — korrigiert

- **Was/zu welchem Steuersatz verkauft/gekauft wurde** → maßgeblich ist **Rechnung/Beleg** (bestimmt die steuerliche Behandlung), **nicht** die Banktransaktion.
- **Ob und wann Geld geflossen ist** → maßgeblich ist die **Banktransaktion**. Bei **EÜR (Ist)** bestimmt der **Zahlungszeitpunkt das Buchungsjahr**.
- **Mengen/Plattformlogik** → Plattformdaten (eBay/PSP), abgeglichen gegen Beleg + Bank.
- **Manuelle Eingaben** → niedrigste Priorität, immer mit Grund dokumentiert.
- **Widerspruch zwischen Beleg und Bank** → `REVIEW_REQUIRED`, nie stillschweigend auflösen.

---

## 8. Fehler-, Review- & Sicherheitslogik

Immer `REVIEW_REQUIRED (Steuerberater)` bei:
- Differenzbesteuerung mit unklarem Einkaufsbeleg
- Annäherung an Schwellen 25.000 € / 100.000 € / 10.000 € OSS
- privat/geschäftlich gemischten Ausgaben
- Reverse-Charge / EU-B2B mit fehlender/ungültiger USt-IdNr
- Import + Einfuhrumsatzsteuer
- E-Rechnung mit Format- oder Geschäftsregelfehler
- Beleg ↔ Bank Betragsdifferenz
- jeder Buchung > definierter Betragsschwelle

Idempotenz-Keys gegen Doppelbuchungen; jede Buchung doppelt geprüft vor Festschreibung.

> Umsetzung siehe [`src/review/queue.py`](../src/review/queue.py).

---

## 9. Audit- & Exportmodus (vorbereitend, nicht abgebend)

Erzeugt jederzeit: Umsatzübersicht (Monat/Jahr), **USt-VA-Vorbereitung** (Zahllast je Satz), GuV/EÜR-Übersicht, OSS-Quartalsaufstellung, **DATEV-/Lexware-Export**, Differenzbesteuerungs-Journal.
**Liefert immer nur Entwürfe** — **die Abgabe via ELSTER/ELSTER-ERiC bleibt menschlicher, freigabepflichtiger Schritt.**

---

## 10. Systemgrenzen — was der Agent NICHT darf/kann

- Keine abschließende Steuerberatung „garantieren", keine Steuerbescheide ersetzen.
- **Keine ELSTER-Abgabe ohne menschliche Freigabe.**
- Keine Daten erfinden.
- Keine Buchung gegen eine `REVIEW_REQUIRED`-Markierung „durchwinken".
- Kein Jahresabschluss ohne Steuerberater-Review.

---

## 11. Tech-Stack & 7-Tage-MVP

**Stack:** Python · PostgreSQL (Prod) / SQLite (MVP) · Claude (Orchestrierung + Klassifikation) · Cloud-OCR (Textract/Document AI) · Lexware Office Public API · eBay/Stripe/PayPal APIs · Bank via Qonto/Finom-API oder Aggregator · Objektspeicher für Belege (WORM/Versionierung) · Audit-Log (append-only) · Telegram („Wizard") als Freigabe-/Review-Interface.

**MVP (7 Tage):**
1. Datenmodell + append-only Audit-Log + Beleg-Storage (unveränderbar)
2. Bank- + eBay-Import (read-only), Reconciliation-Grundlogik
3. OCR-Pipeline + Klassifikation + Review-Queue
4. Differenzbesteuerungs-Tracking pro Artikel
5. E-Rechnungs-Empfang (ZUGFeRD/XRechnung-Parser)
6. Lexware-Export (Draft-Belege via API, Rate-Limit-Backoff)
7. USt-VA-/EÜR-Vorbereitungsreport + Telegram-Freigabe + Auto-Verfahrensdokumentation

**Reihenfolge der Priorität:** Compliance-Fundament (1, 5, 7-Doku) **vor** Komfortfeatures.

---

## Umsetzungsstand (dieses Repository)

| MVP-Punkt | Status | Modul |
|---|---|---|
| 1 — Datenmodell | ✅ | `src/models.py` |
| 1 — Audit-Log (append-only, hash-verkettet) | ✅ | `src/audit/audit_log.py` |
| 1 — Beleg-Storage (WORM, inhaltsadressiert) | ✅ | `src/storage/receipt_store.py` |
| 2 — Bank/eBay-Import + Reconciliation | ⏳ offen | — |
| 3 — OCR-Pipeline | ⏳ offen | — |
| 3 — Review-Queue + REVIEW_REQUIRED-Trigger | ✅ | `src/review/queue.py` |
| 4 — Differenzbesteuerung § 25a (Einzel-/Gesamtdifferenz) | ✅ | `src/tax/differenzbesteuerung.py` |
| 5 — E-Rechnungs-Empfang (XRechnung/ZUGFeRD) | ✅ (Basis) | `src/einvoice/parser.py` |
| 6 — Lexware-Export | ⏳ offen | — |
| 7 — USt-VA-/EÜR-Vorbereitung | ✅ (USt-VA) | `src/tax/ustva.py` |
| 7 — Schwellen-Monitoring 25k/100k/10k | ✅ | `src/tax/schwellen.py` |
| 7 — Auto-Verfahrensdokumentation | ✅ | `src/verfahrensdoku/generator.py` |

Priorisiert wurde — wie in der Spezifikation gefordert — das **Compliance-Fundament**
(Punkte 1, 5, 7-Doku) vor den Komfort-/Integrationsfeatures (2, 3-OCR, 6).
