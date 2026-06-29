"""SKR03/SKR04-Kontentabellen + Kontierungslogik.

WICHTIG: Die Kontonummern sind fachlich uebliche DEFAULTS und mit dem
Steuerberater zu bestaetigen. Sie sind in config.yaml ueberschreibbar.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


# Interne Kategorie -> Standard-Sachkonto (SKR03, Prozessgliederung).
SKR03: dict[str, str] = {
    "erloese": "8400",            # Erloese 19 % USt
    "erloese_kleinunternehmer": "8195",   # Erloese als Kleinunternehmer §19
    "erloese_differenz": "8240",  # Erloese §25a Differenzbesteuerung
    "wareneinkauf": "3200",       # Wareneingang
    "versand": "4910",            # Porto
    "werbung": "4600",            # Werbekosten
    "software": "4980",           # Sonstiger Betriebsbedarf (SaaS/Lizenzen)
    "hosting": "4980",
    "gebuehren": "4760",          # Verkaufsprovisionen (eBay/PayPal/Amazon)
    "bankgebuehren": "4970",      # Nebenkosten des Geldverkehrs
    "telefon": "4920",            # Telefon
    "internet": "4920",
    "buero": "4930",              # Buerobedarf
    "reise": "4670",              # Reisekosten Unternehmer
    "bewirtung": "4650",          # Bewirtungskosten
    "versicherung": "4360",       # Versicherungen
    "steuerberater": "4955",      # Buchfuehrungskosten
    "fahrzeug": "4530",           # Laufende KFZ-Kosten
    "zinsen": "2100",             # Zinsaufwendungen
    "privatentnahme": "1800",     # Privatentnahmen
    "einlage": "1890",            # Privateinlagen
    "sonstiges": "4900",          # Sonstige betriebliche Aufwendungen
}

# Interne Kategorie -> Standard-Sachkonto (SKR04, Abschlussgliederung).
SKR04: dict[str, str] = {
    "erloese": "4400",            # Umsatzerloese 19 % USt
    "erloese_kleinunternehmer": "4185",   # Erloese Kleinunternehmer §19
    "erloese_differenz": "4200",  # Erloese §25a
    "wareneinkauf": "5200",       # Wareneingang
    "versand": "6800",            # Porto
    "werbung": "6600",            # Werbekosten
    "software": "6837",           # EDV-/Software-Aufwand
    "hosting": "6837",
    "gebuehren": "6770",          # Verkaufsprovisionen
    "bankgebuehren": "6855",      # Nebenkosten des Geldverkehrs
    "telefon": "6805",            # Telefon
    "internet": "6805",
    "buero": "6815",              # Buerobedarf
    "reise": "6673",              # Reisekosten Unternehmer
    "bewirtung": "6640",          # Bewirtungskosten
    "versicherung": "6400",       # Versicherungen
    "steuerberater": "6827",      # Buchfuehrungskosten
    "fahrzeug": "6530",           # Laufende KFZ-Kosten
    "zinsen": "7300",             # Zinsaufwendungen
    "privatentnahme": "2100",     # Privatentnahmen
    "einlage": "2180",            # Privateinlagen
    "sonstiges": "6300",          # Sonstige betriebliche Aufwendungen
}

# Umsatzsteuer-Schluessel je Kategorie (DATEV-konventionell).
#   "" = kein automatischer Schluessel (Kleinunternehmer/§25a/0 % -> Review/Sonderfall)
UST_SCHLUESSEL: dict[str, str] = {
    "erloese": "",                # Standard-USt 19 % (DATEV-Automatikkonto traegt es)
    "erloese_kleinunternehmer": "",
    "erloese_differenz": "",
    "wareneinkauf": "9",          # Vorsteuer 19 % (sofern abziehbar)
    "versand": "9",
    "werbung": "9",
    "software": "9",
    "gebuehren": "9",
    "buero": "9",
}


@dataclass
class Buchungssatz:
    """Ergebnis der Kontierung — Soll/Haben bleibt bewusst offen (Berater/Lexware)."""
    kategorie: str
    konto: str
    betrag: Decimal
    rahmen: str                   # "skr03" | "skr04"
    ust_schluessel: str = ""
    hinweis: str = ""

    @property
    def sicher(self) -> bool:
        return bool(self.konto)


def _tabelle(rahmen: str, config: dict | None) -> dict:
    basis = dict(SKR04 if rahmen == "skr04" else SKR03)
    if config:
        basis.update({k: str(v) for k, v in (config.get(rahmen, {}) or {}).items()})
    return basis


def konto_fuer(kategorie: str, *, rahmen: str = "skr03",
               config: dict | None = None) -> str:
    """Gibt die Kontonummer fuer eine Kategorie zurueck ('' wenn unbekannt)."""
    return _tabelle(rahmen, config).get((kategorie or "").lower(), "")


def kontiere(kategorie: str, betrag, *, rahmen: str = "skr03",
             config: dict | None = None) -> Buchungssatz:
    """Erzeugt einen Buchungssatz-Vorschlag. Unbekannte Kategorie -> konto='' (Review)."""
    kat = (kategorie or "sonstiges").lower()
    konto = konto_fuer(kat, rahmen=rahmen, config=config)
    ust = UST_SCHLUESSEL.get(kat, "")
    hinweis = "" if konto else f"Keine Kontozuordnung fuer '{kat}' — Review noetig."
    return Buchungssatz(kategorie=kat, konto=konto, betrag=Decimal(str(betrag)),
                        rahmen=rahmen, ust_schluessel=ust, hinweis=hinweis)
