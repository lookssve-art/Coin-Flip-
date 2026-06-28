"""Steuer-/Buchhaltungs-Wissensbasis (Rechtsstand 2025/2026, DE).

Kuratierte, mit Fundstellen versehene Eintraege zu allen Themen der Spezifikation.
Der Telegram-Bot durchsucht diese Basis per Schlagwort; optional kann eine
Claude-gestuetzte Antwort die Treffer als Grundlage (Grounding) nutzen.

WICHTIG: Dies ist allgemeine Information, keine Steuerberatung. Im Zweifel
Steuerberater. (Abschnitt 0 der Spezifikation.)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Eintrag:
    schlagwort: str
    aliase: tuple
    text: str
    quelle: str = ""


EINTRAEGE: list[Eintrag] = [
    Eintrag(
        "E-Rechnung",
        ("erechnung", "e-rechnung", "xrechnung", "zugferd", "factur-x", "elektronische rechnung"),
        "Empfangspflicht seit 01.01.2025 — ausnahmslos, auch fuer Kleinunternehmer. "
        "Strukturierte Formate: XRechnung (reines XML) bzw. ZUGFeRD/Factur-X (PDF/A-3 + XML). "
        "Eine PDF ohne strukturierten Datensatz ist KEINE E-Rechnung. Versandpflicht "
        "gestaffelt: 2025-2026 Uebergangsfrist, ab 2027 fuer >800.000 EUR Vorjahresumsatz, "
        "ab 2028 fuer alle im inlaendischen B2B. Kleinunternehmer sind vom Ausstellen befreit, "
        "muessen aber empfangen. Archivierung: Originalformat 8 Jahre elektronisch.",
        "§ 14 UStG; Wachstumschancengesetz",
    ),
    Eintrag(
        "Aufbewahrungsfristen",
        ("aufbewahrung", "frist", "fristen", "wie lange", "aufheben", "archivierung"),
        "8 Jahre: Buchungsbelege & Rechnungen (seit 01.01.2025, BEG IV). "
        "10 Jahre: Buecher, Aufzeichnungen, Inventare, Jahresabschluss, "
        "Verfahrensdokumentation. 6 Jahre: Handels-/Geschaeftsbriefe (auch E-Mails). "
        "Fristbeginn: Schluss des Kalenderjahres der letzten Bearbeitung. "
        "Sicherheitsregel: im Zweifel 10 Jahre ansetzen.",
        "§ 147 AO; § 257 HGB",
    ),
    Eintrag(
        "Kleinunternehmer",
        ("kleinunternehmer", "ku", "§19", "paragraph 19", "25000", "100000", "steuerbefreiung"),
        "Reformiert ab 01.01.2025: Vorjahresgrenze 25.000 EUR (netto) UND laufendes Jahr "
        "100.000 EUR — beide muessen erfuellt sein. Die 100.000 EUR sind eine harte Grenze "
        "(Fallbeileffekt): der Umsatz, mit dem sie gerissen wird, ist bereits voll "
        "regelbesteuert. Es ist nun eine Steuerbefreiung (Pruefung auf Nettoumsaetze). "
        "KEIN Vorsteuerabzug (auch nicht auf Importe/EUSt). Wer Vorsteuer ziehen will, "
        "muss zur Regelbesteuerung optieren (bindet 5 Jahre). Fuer eBay-EU-Verkaeufe ist "
        "trotzdem eine USt-IdNr noetig.",
        "§ 19 UStG",
    ),
    Eintrag(
        "GoBD",
        ("gobd", "verfahrensdokumentation", "unveraenderbarkeit", "nachvollziehbar",
         "ordnungsmaessig"),
        "Grundsaetze ordnungsmaessiger Buchfuehrung (digital). Gelten auch fuer "
        "Kleinunternehmer und EUR-Rechner, sobald EDV im Spiel ist. Kernanforderungen: "
        "Nachvollziehbarkeit, Vollstaendigkeit, Richtigkeit, Zeitgerechtigkeit, Ordnung, "
        "Unveraenderbarkeit, maschinelle Auswertbarkeit. Editierbare Word-/PDF-Dateien sind "
        "GoBD-widrig (keine Unveraenderbarkeit). Verfahrensdokumentation ist Pflicht und so "
        "lange aufzubewahren wie die zugehoerigen Unterlagen (10 Jahre). Ersetzendes Scannen "
        "nur mit protokolliertem Prozess.",
        "GoBD (BMF-Schreiben); § 146, § 147 AO",
    ),
    Eintrag(
        "Differenzbesteuerung",
        ("differenzbesteuerung", "§25a", "paragraph 25a", "marge", "gebrauchtware",
         "sammlerware", "einzeldifferenz", "gesamtdifferenz"),
        "Besteuert wird nur die Marge (Verkauf - Einkauf), typisch bei Ankauf von "
        "Privatpersonen ohne Vorsteuer. USt darf NICHT offen ausgewiesen werden. Erfordert "
        "artikelgenaue Einkaufspreis-Erfassung. Methoden: Einzeldifferenz oder "
        "Gesamtdifferenz (nur fuer Einzelposten <= 750 EUR). Negative Margen erzeugen keine "
        "negative USt. § 25a-Ware faellt NICHT unter die OSS-Fernverkaufsregelung.",
        "§ 25a UStG",
    ),
    Eintrag(
        "OSS / Fernverkauf",
        ("oss", "one-stop-shop", "fernverkauf", "lieferschwelle", "10000", "10.000", "eu-verkauf"),
        "EU-weite Lieferschwelle 10.000 EUR netto (Summe ALLER B2C-Fernverkaeufe in alle "
        "EU-Laender zusammen). Darueber: Besteuerung im Bestimmungsland, zentrale "
        "Quartalsmeldung ueber OSS beim BZSt statt lokaler Registrierungen. Ausnahme: "
        "Lieferungen unter Differenzbesteuerung (§ 25a) fallen NICHT unter die "
        "Fernverkaufsregelung — bleiben in Deutschland steuerpflichtig, kein OSS noetig.",
        "§ 3c UStG; § 18j UStG (OSS)",
    ),
    Eintrag(
        "EÜR",
        ("euer", "eur", "einnahmen-ueberschuss", "zufluss", "abfluss", "ist-prinzip", "gewinn"),
        "Einnahmen-Ueberschuss-Rechnung: Regelfall fuer kleine Einzelunternehmen. "
        "Ist-Prinzip / Zufluss-Abfluss -> der Zahlungszeitpunkt (Bank) bestimmt das "
        "Buchungsjahr. Anlage EUR ist elektronisch ueber ELSTER abzugeben.",
        "§ 4 Abs. 3 EStG",
    ),
    Eintrag(
        "Gewerbesteuer",
        ("gewerbesteuer", "gewst", "freibetrag", "24500", "24.500"),
        "Freibetrag 24.500 EUR Gewinn fuer Einzelunternehmer und Personengesellschaften. "
        "Erst der darueber liegende Gewerbeertrag wird mit Gewerbesteuer belegt.",
        "§ 11 Abs. 1 GewStG",
    ),
    Eintrag(
        "USt-Voranmeldung",
        ("ustva", "ust-va", "voranmeldung", "dauerfristverlaengerung", "rhythmus"),
        "Rhythmus (monatlich/quartalsweise/jaehrlich) gibt das Finanzamt vor; in den ersten "
        "beiden Jahren der Regelbesteuerung oft monatlich. Dauerfristverlaengerung moeglich "
        "(verschiebt die Abgabe um einen Monat, bei Monatszahlern gegen Sondervorauszahlung). "
        "Abgabe via ELSTER — bleibt menschlicher, freigabepflichtiger Schritt.",
        "§ 18 UStG; § 46-48 UStDV",
    ),
    Eintrag(
        "Einfuhrumsatzsteuer / Zoll",
        ("einfuhrumsatzsteuer", "eust", "zoll", "import", "aliexpress", "150 euro", "freigrenze"),
        "Wegfall der 150-EUR-Zollfreigrenze (2026): fuer nahezu jede Importsendung koennen "
        "Zoll + Einfuhrumsatzsteuer anfallen. Import-Belege + EUSt sind separat zu erfassen. "
        "Als Kleinunternehmer ist die EUSt NICHT als Vorsteuer abziehbar.",
        "§ 1 Abs. 1 Nr. 4 UStG; UZK",
    ),
    Eintrag(
        "Reverse-Charge",
        ("reverse-charge", "reverse charge", "§13b", "paragraph 13b", "b2b eu", "ust-idnr"),
        "Bei B2B-Leistungen/Lieferungen innerhalb der EU mit gueltiger USt-IdNr geht die "
        "Steuerschuld auf den Leistungsempfaenger ueber (keine offene USt). Voraussetzung: "
        "gueltige USt-IdNr des Empfaengers (qualifizierte Bestaetigung beim BZSt). Fehlt/"
        "ungueltig -> REVIEW_REQUIRED.",
        "§ 13b UStG",
    ),
    Eintrag(
        "Vorsteuerabzug",
        ("vorsteuer", "vorsteuerabzug", "§15", "paragraph 15"),
        "Abzug der in Eingangsrechnungen ausgewiesenen USt — nur bei Regelbesteuerung und "
        "ordnungsgemaesser Rechnung mit allen Pflichtangaben. Kleinunternehmer haben KEINEN "
        "Vorsteuerabzug. Gemischt privat/geschaeftliche Ausgaben sind aufzuteilen.",
        "§ 15 UStG",
    ),
    Eintrag(
        "USt-Saetze",
        ("ust-satz", "steuersatz", "mwst", "19", "7", "ermaessigt"),
        "Regelsatz 19 %, ermaessigter Satz 7 % (z. B. Buecher). In Lexware Office zulaessig: "
        "0/5/7/16/19 %. Bei Differenzbesteuerung wird die USt aus der Marge herausgerechnet "
        "und nicht offen ausgewiesen.",
        "§ 12 UStG",
    ),
    Eintrag(
        "USt-IdNr",
        ("ust-idnr", "umsatzsteuer-identifikationsnummer", "bzst", "vat id"),
        "Beim BZSt zu beantragen. Fuer eBay-EU-Verkaeufe Pflicht (bei eBay hinterlegen) — "
        "auch fuer Kleinunternehmer. Bei eBay verlangt die Plattform bei Ueberschreiten der "
        "10k-Schwelle die OSS-Bestaetigung oder hinterlegte USt-IdNr, sonst Kontosperre.",
        "§ 27a UStG",
    ),
    Eintrag(
        "Verpackungsregister / LUCID",
        ("lucid", "verpackungsregister", "verpackg", "verpackung"),
        "Registrierung im Verpackungsregister LUCID + Mengenmeldung sind Pflicht fuer "
        "Versandhaendler. Der Agent erinnert/trackt, bucht aber nicht.",
        "VerpackG",
    ),
    Eintrag(
        "DSGVO",
        ("dsgvo", "datenschutz", "kundendaten", "loeschkonzept"),
        "Kundendaten (Namen, Adressen) sind personenbezogen. Speicherung, Zugriff und "
        "Loeschkonzept sind zu dokumentieren.",
        "DSGVO / BDSG",
    ),
    Eintrag(
        "Deemed Supplier",
        ("deemed supplier", "elektronische schnittstelle", "marktplatz", "ebay fuehrt ab"),
        "eBay kann in bestimmten Konstellationen als elektronische Schnittstelle die USt "
        "selbst abfuehren (deemed supplier). Dann darf dieselbe USt nicht erneut angesetzt "
        "werden — eBay-Steuerreports gegen die eigene Buchung abgleichen "
        "(Doppelversteuerung vermeiden).",
        "§ 3 Abs. 3a UStG",
    ),
    Eintrag(
        "Rechnungspflichtangaben",
        ("rechnung", "pflichtangaben", "rechnungsangaben", "was muss auf die rechnung"),
        "Pflichtangaben einer Rechnung: vollstaendiger Name + Anschrift von Leistendem und "
        "Empfaenger, Steuernummer oder USt-IdNr, Ausstellungsdatum, fortlaufende "
        "Rechnungsnummer, Menge/Art der Leistung, Liefer-/Leistungsdatum, Entgelt nach "
        "Steuersaetzen aufgeschluesselt, Steuersatz + Steuerbetrag (bzw. Hinweis auf "
        "Steuerbefreiung). Kleinunternehmer: Hinweis 'Kein Steuerausweis wegen § 19 UStG'.",
        "§ 14 Abs. 4 UStG",
    ),
    Eintrag(
        "Kleinbetragsrechnung",
        ("kleinbetragsrechnung", "250 euro", "kleinbetrag", "quittung", "bon"),
        "Bis 250 EUR brutto genuegen vereinfachte Angaben: Name + Anschrift des Leistenden, "
        "Ausstellungsdatum, Menge/Art, Entgelt + Steuerbetrag in einer Summe, Steuersatz. "
        "Keine Rechnungsnummer/Empfaengerangaben noetig. Von der E-Rechnungspflicht ausgenommen.",
        "§ 33 UStDV",
    ),
    Eintrag(
        "Betriebsausgaben",
        ("betriebsausgaben", "absetzen", "abziehbar", "ausgaben"),
        "Aufwendungen, die durch den Betrieb veranlasst sind, mindern den Gewinn. Gemischt "
        "privat/betrieblich -> aufteilen. Nicht/teilweise abziehbar: u. a. Geschenke > 50 EUR/"
        "Empfaenger, Bewirtung nur zu 70 %, private Anteile. Belegnachweis erforderlich.",
        "§ 4 Abs. 4, Abs. 5 EStG",
    ),
    Eintrag(
        "AfA / Abschreibung",
        ("afa", "abschreibung", "anlagevermoegen", "nutzungsdauer"),
        "Wirtschaftsgueter ueber 800 EUR netto werden ueber die betriebsgewoehnliche "
        "Nutzungsdauer abgeschrieben (lineare AfA), nicht sofort voll als Ausgabe gebucht. "
        "Maszgeblich sind die amtlichen AfA-Tabellen.",
        "§ 7 EStG",
    ),
    Eintrag(
        "GWG",
        ("gwg", "geringwertige wirtschaftsgueter", "800 euro", "sofortabschreibung"),
        "Geringwertige Wirtschaftsgueter bis 800 EUR netto koennen im Anschaffungsjahr sofort "
        "voll als Betriebsausgabe abgesetzt werden (statt AfA ueber Jahre). Alternativ "
        "Sammelposten/Poolabschreibung.",
        "§ 6 Abs. 2 EStG",
    ),
    Eintrag(
        "Ist- vs. Soll-Versteuerung",
        ("ist-versteuerung", "soll-versteuerung", "istversteuerung", "vereinnahmte entgelte"),
        "Soll-Versteuerung (Regel): USt entsteht mit Leistungserbringung (Rechnungsdatum). "
        "Ist-Versteuerung (auf Antrag, u. a. bis 800.000 EUR Vorjahresumsatz): USt entsteht "
        "erst mit Zahlungseingang — schont die Liquiditaet. Passt zur EUR (Zufluss/Abfluss).",
        "§ 13, § 20 UStG",
    ),
    Eintrag(
        "Storno / Refund buchen",
        ("storno", "refund", "erstattung", "ruecksendung", "chargeback", "gutschrift buchen"),
        "Eine Erstattung/Ruecksendung mindert den urspruenglichen Umsatz (und die USt) im "
        "Zeitpunkt der Rueckzahlung. Differenzbesteuerung: die Marge des stornierten Verkaufs "
        "entfaellt. Chargebacks gegen den Zahlungsdienst-/Bankbeleg abgleichen.",
        "§ 17 UStG",
    ),
    Eintrag(
        "Privatentnahme",
        ("privatentnahme", "entnahme", "eigenverbrauch", "privat genutzt"),
        "Wird ein betriebliches Wirtschaftsgut/Geld privat entnommen, ist das als "
        "Privatentnahme zu erfassen (kein Betriebsaufwand). Bei USt-Pflichtigen kann eine "
        "unentgeltliche Wertabgabe USt ausloesen.",
        "§ 4 Abs. 1, § 6 Abs. 1 Nr. 4 EStG",
    ),
    Eintrag(
        "Inventur / Warenbestand",
        ("inventur", "bestand", "warenbestand", "lager", "vorrat"),
        "Bei der EUR ist grundsaetzlich keine Inventur noetig (Wareneinkauf ist im "
        "Zahlungsjahr Betriebsausgabe). Dennoch ist eine Bestandsuebersicht sinnvoll — und "
        "fuer die Differenzbesteuerung sind artikelgenaue Einkaufspreise ohnehin Pflicht.",
        "§ 4 Abs. 3 EStG",
    ),
    Eintrag(
        "Steuernummer vs. USt-IdNr",
        ("steuernummer", "stnr", "unterschied steuernummer ust-idnr"),
        "Die Steuernummer vergibt das Finanzamt fuer die Einkommen-/Umsatzsteuer im Inland. "
        "Die USt-IdNr (BZSt) ist fuer den EU-grenzueberschreitenden Verkehr (B2B, OSS, eBay-EU). "
        "Auf Rechnungen genuegt eine der beiden.",
        "§ 14 Abs. 4, § 27a UStG",
    ),
]


def _normalize(s: str) -> str:
    s = (s or "").lower()
    s = (s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss"))
    return s


@dataclass
class Treffer:
    eintrag: Eintrag
    score: int


@dataclass
class Duden:
    eintraege: list = field(default_factory=lambda: list(EINTRAEGE))

    def liste(self) -> list[str]:
        return [e.schlagwort for e in self.eintraege]

    def suche(self, query: str, limit: int = 3) -> list[Eintrag]:
        """Schlagwort-/Volltextsuche; liefert die besten Treffer (kann leer sein)."""
        q = _normalize(query)
        tokens = [t for t in re.split(r"\W+", q) if len(t) >= 3]
        treffer: list[Treffer] = []
        for e in self.eintraege:
            score = 0
            hay_titel = _normalize(e.schlagwort)
            hay_alias = " ".join(_normalize(a) for a in e.aliase)
            hay_text = _normalize(e.text)
            # Direkter Alias-/Titeltreffer wiegt am schwersten.
            for a in e.aliase:
                if _normalize(a) and _normalize(a) in q:
                    score += 5
            for tok in tokens:
                if tok in hay_titel:
                    score += 4
                elif tok in hay_alias:
                    score += 3
                elif tok in hay_text:
                    score += 1
            if score:
                treffer.append(Treffer(e, score))
        treffer.sort(key=lambda t: t.score, reverse=True)
        return [t.eintrag for t in treffer[:limit]]

    def formatiere(self, eintrag: Eintrag) -> str:
        quelle = f"\n\n📖 {eintrag.quelle}" if eintrag.quelle else ""
        return f"*{eintrag.schlagwort}*\n\n{eintrag.text}{quelle}"
