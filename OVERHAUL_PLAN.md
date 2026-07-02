# OVERHAUL_PLAN — SERO eBay→Lexware Accounting Agent

Abgleich des Umbau-Auftrags (AGENT_OVERHAUL_PROMPT) gegen den Ist-Stand des Repos.
Legende: ✅ vorhanden · 🟡 teilweise · 🔴 fehlt/zu bauen · ❓ Entscheidung nötig

## 0. Kontext / Grundsatz
- Bestehender Agent refactoren statt neu schreiben ✅ (Repo ist modular, Stdlib-Kern)
- Immer Entwurf, Finalisierung nur nach Telegram-Freigabe → 🟡 (Draft-Push da,
  Finalize-nach-Freigabe-Flow mit Buttons fehlt)

## 1. Architektur
| Soll | Ist | Delta |
|------|-----|-------|
| State Machine je Order (NEW→FETCHED→CALCULATED→DRAFT_CREATED→APPROVED/REJECTED→FINALIZED) | idempotentes Register (1 Beleg/Order) | 🔴 echte State-Machine + Statusfeld |
| Idempotenz über eBay orderId | ✅ Register/Reconciliation nach ID | ✅ |
| Decimal, ROUND_HALF_UP | ✅ durchgängig | ✅ |
| SQLite (orders, vouchers, state) | JSON-Dateien | ❓ SQLite vs. JSON (JSON reicht funktional; SQLite = sauberere State-Machine) |
| Fable-5 als Agent-Core | Modell = claude-opus-4-8 | 🟡 auf `claude-fable-5` umstellen (config) |

## 2. eBay-Seite
| Soll | Ist | Delta |
|------|-----|-------|
| Bestellungen (Positionen, Versand, Land, Zahlstatus) | Trading-API GetOrders | 🟡 Fulfillment-API optional; Trading liefert das Nötige |
| Finances getTransactions: Gebühren (FVF, Anzeigen, Zahlung), Auszahlungen, Erstattungen | ✅ ebay-finances (signiert), Werbung+Versand getrennt | ✅ |
| Gebühren **pro Order** zuordnen | aggregiert (Summe) | 🔴 pro-Order-Zuordnung |
| Versandlabels aus Finances; sonst Kostentabelle (DHL/Hermes) je Order via Telegram überschreibbar | eBay-Label ✅; externe via ausgaben.csv | 🟡 Kostentabelle + Telegram-Override |
| Raw-JSON je Order archivieren (GoBD) | Exporte gespeichert | 🔴 pro-Order-Raw-Archiv + Hash |

## 3. Steuerlogik — HERZSTÜCK  ❓❓❓
**KRITISCH / offene Grundsatzfrage:** Der Auftrag beschreibt **Regelbesteuerung**
(§25a-Margen-USt mit 19/119 **und** 19 % auf Neuware). Die aktuelle `config.yaml`
steht auf **Kleinunternehmer §19 (keine USt)**. Das schließt sich gegenseitig aus
und ändert die gesamte Steuerlogik. → **muss vor jedem Steuer-Code geklärt werden.**

| Soll | Ist | Delta |
|------|-----|-------|
| Steuer-Flag je Artikel, Default per Kategorie, via Telegram korrigierbar | tax_scheme je Verkauf (differenz/regel) | 🔴 pro-Artikel-Flag + Telegram-Korrektur |
| §25a: kein USt-Ausweis, Pflichthinweis „Sonderregelung/Gebrauchtgegenstände (§25a UStG)", USt=(VK−EK)×19/119 intern | §25a-Journal + Margen-USt vorhanden; Rechnungshinweis = Kleinunternehmer | 🟡 §25a-Hinweistext + Beleg-taxType |
| EK je Artikel erfassbar, Telegram-Rückfrage wenn EK fehlt | einkaufspreise aus eBay-Käufen | 🔴 Telegram-EK-Rückfrage-Flow |
| Regelbesteuerung 19 % auf Neuware, Brutto+19 % im Beleg | Struktur da (TaxScheme.REGEL) | 🟡 Beleg-Ausweis 19 % |
| Versand = Nebenleistung (teilt Steuersatz der Hauptleistung) | Versand als eigene Ausgabe | 🔴 Versand-Steuerlogik als Nebenleistung |
| Drittland (CH/UK/US): steuerfreie Ausfuhr §4/§6, Ausfuhrnachweis anhängen | Land wird erfasst | 🔴 Ausfuhr-Logik + Nachweis |
| eBay-Gebühren = Reverse Charge §13b (eBay Luxemburg) | Gebühren als Ausgabe | 🔴 §13b-Steuerschlüssel + Monatsrechnung anhängen |
| Plausi-Check: Σ Positionen == Auszahlung + Gebühren cent-genau, sonst Telegram-Diff | Plausi-Modul da (IBAN/USt-ID/Arithmetik) | 🟡 Auszahlungs-Abgleich als Anlege-Gate |

## 4. Lexware-Seite  ❗ wichtige Korrektur
| Soll | Ist | Delta |
|------|-----|-------|
| eBay-Verkäufe über **/v1/vouchers** (Einnahmebeleg/salesinvoice), NICHT /v1/invoices; Erstattungen = salescreditnote | wir nutzen **/v1/invoices** (Rechnungserstellung) | ❓/🔴 auf Voucher-Endpunkt umstellen |
| Spaltenmethode: Positionen je Kategorie+Steuersatz gruppieren, exakt wie Lexware rechnen | Rechnung mit Einzelpositionen | 🔴 Spaltenmethode |
| Draft-first, Finalize nur nach Freigabe; festgeschriebene Belege unveränderbar (Status prüfen) | Draft-Push ✅, Finalize-Gate 🟡 | 🟡 Status-Prüfung + Finalize-Flow |
| Sammel-Kunde default (keine Einzelkontakte); Käufer+OrderID im Buchungstext; Option echter Kontakt (B2B) | Käufername in Rechnungsadresse | 🔴 Sammel-Kunde + Buchungstext |
| File-Upload: Order-JSON (als PDF) + Label/Ausfuhrnachweis an Voucher | — | 🔴 File-Upload |
| Rate-Limits (429 Backoff) | rate_limit_rps in config, Client schlicht | 🟡 Backoff/Retry |
| Webhooks (invoice.status.changed) optional, nicht MVP | — | ⏭ später |

## 5. Telegram (Fable-5)
| Soll | Ist | Delta |
|------|-----|-------|
| Push je Verkauf: Karte (Artikel, VK, Versand, Gebühren, Steuerart, Marge, Lexware-Entwurf-ID) + Inline-Buttons Freigeben/Korrigieren/Verwerfen | Push + /commands + Review-Queue | 🔴 Inline-Buttons + Freigabe-Finalize |
| Freitext an Fable-5 mit Tool-Use: set_ek, set_tax_mode, report, status, resync | /duden (LLM), /sync, /report | 🔴 Tool-Use-Kommandos (set_ek/set_tax_mode/resync) |
| Monatsreport-Command | /bwa | 🟡 an Soll-Felder anpassen |
| Fehler-Alarme (API down, Validierung, OSS) proaktiv | Schwellen-/Review-Meldungen | 🟡 erweitern |

## 6. GoBD & Compliance
- Append-only Journal mit Timestamp + Payload-Hash → ✅ (audit/ hash-verkettet)
- Raw-Daten unveränderbar archivieren + Hash + an Belege → 🔴
- VERFAHRENSDOKUMENTATION.md → ✅ Generator vorhanden
- E-Rechnung B2B (XRechnung/ZUGFeRD über Lexware) → 🟡 B2B-Flag setzen

## 7. Vorgehen (lt. Auftrag)
1. OVERHAUL_PLAN.md (dieses Dokument) → **Bestätigung abwarten**
2. Live-Docs lesen (Lexware/eBay) — ⚠️ **in dieser Umgebung nicht möglich**
   (Netzwerksperre 403 zu developers.lexware.io/developer.ebay.com). taxType-Werte
   müssen daher auf deinem Mac verifiziert oder von dir bestätigt werden.
3. Refactor + pytest (≥15 Steuerfälle, echte Cent-Beträge)
4. Sandbox-Default; PRODUCTION=true erst nach manuellem Flag
5. README + RUNBOOK

## Offene Entscheidungen (blockierend)
1. **Steuerstatus:** Kleinunternehmer §19 (aktuell, keine USt) **ODER**
   Regelbesteuerung + §25a-Margen-USt (wie im Auftrag)? — ändert die ganze Steuerlogik.
2. **Lexware-Buchung:** eBay-Verkäufe als **Voucher** (Einnahmebeleg, lt. Auftrag)
   statt als **Invoice** (aktuell)? — Architektur-Umstellung.
3. **Modell:** Agent-Core auf `claude-fable-5` umstellen? (aktuell opus-4-8)

## Ehrliche Constraints dieser Umgebung
- Kein Zugriff auf deinen Mac; kein Netz zu eBay/Lexware/Docs (403-Policy).
  Der Live-Betrieb + Doc-Verifikation läuft auf deinem MacBook.
