"""BWA-Berechnung aus EÜR-Auswertung + Verkaufsliste."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

from ..kontierung import konto_fuer


def _q(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _prozent(zaehler: Decimal, nenner: Decimal) -> Decimal:
    if nenner == 0:
        return Decimal("0.0")
    return (zaehler / nenner * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


@dataclass
class BWA:
    zeitraum: str
    umsatz: Decimal
    wareneinkauf: Decimal
    rohertrag: Decimal
    kosten_je_kategorie: dict           # {kategorie: {"betrag", "konto"}}
    kosten_gesamt: Decimal              # ohne Wareneinkauf
    gewinn: Decimal
    rohertragsquote: Decimal            # Rohertrag / Umsatz %
    kostenquote: Decimal                # Kosten / Umsatz %
    gewinnmarge: Decimal                # Gewinn / Umsatz %
    monatlich: dict = field(default_factory=dict)   # {"2026-06": {"umsatz","anzahl"}}
    anzahl_verkaeufe: int = 0


def erstelle_bwa(sales, euer, *, zeitraum: str = "laufend", rahmen: str = "skr03",
                 config: dict | None = None) -> BWA:
    """Baut die BWA aus der EÜR (``euer``) + den Verkaeufen.

    ``euer`` muss ``einnahmen_gesamt``, ``ausgaben_je_kategorie`` und ``gewinn``
    bieten (``src.tax.euer.EUER``). Wareneinkauf wird aus den Kosten herausgeloest,
    um den Rohertrag zu zeigen.
    """
    umsatz = _q(euer.einnahmen_gesamt)
    kosten = {k: _q(v) for k, v in (euer.ausgaben_je_kategorie or {}).items()}
    wareneinkauf = kosten.pop("wareneinkauf", Decimal("0"))
    rohertrag = _q(umsatz - wareneinkauf)
    kosten_gesamt = _q(sum(kosten.values(), Decimal("0")))
    gewinn = _q(euer.gewinn)

    kosten_je_kat = {
        kat: {"betrag": betrag, "konto": konto_fuer(kat, rahmen=rahmen, config=config)}
        for kat, betrag in sorted(kosten.items(), key=lambda kv: kv[1], reverse=True)
    }

    monatlich: dict = {}
    for s in sales:
        monat = getattr(s, "datum", None)
        if monat is None:
            continue
        key = f"{monat.year:04d}-{monat.month:02d}"
        eintrag = monatlich.setdefault(key, {"umsatz": Decimal("0"), "anzahl": 0})
        eintrag["umsatz"] += Decimal(str(getattr(s, "brutto", "0")))
        eintrag["anzahl"] += 1
    monatlich = {k: {"umsatz": _q(v["umsatz"]), "anzahl": v["anzahl"]}
                 for k, v in sorted(monatlich.items())}

    return BWA(
        zeitraum=zeitraum, umsatz=umsatz, wareneinkauf=wareneinkauf,
        rohertrag=rohertrag, kosten_je_kategorie=kosten_je_kat,
        kosten_gesamt=kosten_gesamt, gewinn=gewinn,
        rohertragsquote=_prozent(rohertrag, umsatz),
        kostenquote=_prozent(kosten_gesamt + wareneinkauf, umsatz),
        gewinnmarge=_prozent(gewinn, umsatz),
        monatlich=monatlich, anzahl_verkaeufe=len(list(sales)),
    )


def render_bwa_text(b: BWA) -> str:
    z = []
    z.append(f"BWA ({b.zeitraum}) — {b.anzahl_verkaeufe} Verkaeufe")
    z.append("=" * 44)
    z.append(f"Umsatz                {b.umsatz:>12} EUR")
    z.append(f"− Wareneinkauf        {b.wareneinkauf:>12} EUR")
    z.append(f"= Rohertrag           {b.rohertrag:>12} EUR  ({b.rohertragsquote} %)")
    z.append("-" * 44)
    for kat, info in b.kosten_je_kategorie.items():
        konto = f"[{info['konto']}]" if info["konto"] else "[?]"
        z.append(f"  {kat:<16}{konto:>7}{info['betrag']:>13} EUR")
    z.append(f"= Kosten gesamt       {b.kosten_gesamt:>12} EUR  ({b.kostenquote} %)")
    z.append("=" * 44)
    z.append(f"GEWINN                {b.gewinn:>12} EUR  ({b.gewinnmarge} %)")
    if b.monatlich:
        z.append("")
        z.append("Monatsverlauf (Umsatz):")
        for monat, info in b.monatlich.items():
            z.append(f"  {monat}: {info['umsatz']:>10} EUR ({info['anzahl']} Verk.)")
    return "\n".join(z)


def schreibe_bwa_csv(pfad: str, b: BWA) -> None:
    import os
    os.makedirs(os.path.dirname(pfad) or ".", exist_ok=True)
    with open(pfad, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["Position", "Konto", "Betrag_EUR"])
        w.writerow(["Umsatz", "", b.umsatz])
        w.writerow(["Wareneinkauf", konto_fuer("wareneinkauf"), b.wareneinkauf])
        w.writerow(["Rohertrag", "", b.rohertrag])
        for kat, info in b.kosten_je_kategorie.items():
            w.writerow([kat, info["konto"], info["betrag"]])
        w.writerow(["Kosten_gesamt", "", b.kosten_gesamt])
        w.writerow(["Gewinn", "", b.gewinn])
        w.writerow(["Rohertragsquote_%", "", b.rohertragsquote])
        w.writerow(["Kostenquote_%", "", b.kostenquote])
        w.writerow(["Gewinnmarge_%", "", b.gewinnmarge])
        for monat, info in b.monatlich.items():
            w.writerow([f"Umsatz_{monat}", "", info["umsatz"]])
