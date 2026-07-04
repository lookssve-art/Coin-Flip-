"""Warenbuch-Berechnung: Käufe + Verkäufe -> Bestand + Marge je Artikelgruppe."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP


def _q(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _key(text: str) -> str:
    """Normalisiert Artikelbezeichnung/SKU zu einem Gruppierungs-Schluessel."""
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t[:60] or "unbekannt"


@dataclass
class Gruppe:
    schluessel: str
    bezeichnung: str
    einkauf_anzahl: int = 0
    einkauf_summe: Decimal = Decimal("0")
    verkauf_anzahl: int = 0
    verkauf_summe: Decimal = Decimal("0")
    quellen: set = field(default_factory=set)

    @property
    def bestand(self) -> int:
        return self.einkauf_anzahl - self.verkauf_anzahl

    @property
    def marge(self) -> Decimal:
        # grobe Marge: Verkaufserloese minus Einkauf (nur informativ)
        return _q(self.verkauf_summe - self.einkauf_summe)


@dataclass
class Warenbuch:
    gruppen: dict                       # schluessel -> Gruppe
    einkauf_gesamt: Decimal
    verkauf_gesamt: Decimal
    einkauf_anzahl: int
    verkauf_anzahl: int

    @property
    def bestand_anzahl(self) -> int:
        return self.einkauf_anzahl - self.verkauf_anzahl

    @property
    def roh_marge(self) -> Decimal:
        return _q(self.verkauf_gesamt - self.einkauf_gesamt)


def erstelle_warenbuch(kaeufe, verkaeufe) -> Warenbuch:
    """Baut das Warenbuch.

    ``kaeufe``: Iterable von Dicts {product_id|title, preis|betrag, quelle}
    ``verkaeufe``: Iterable von PlatformSale (oder Dicts mit product_name/brutto).
    """
    gruppen: dict[str, Gruppe] = {}

    def hol(schluessel: str, bez: str) -> Gruppe:
        g = gruppen.get(schluessel)
        if g is None:
            g = Gruppe(schluessel=schluessel, bezeichnung=bez)
            gruppen[schluessel] = g
        return g

    ek_ges = Decimal("0")
    ek_n = 0
    for k in kaeufe:
        bez = str(k.get("title") or k.get("product_id") or k.get("kontakt") or "unbekannt")
        preis = Decimal(str(k.get("preis") or k.get("betrag") or "0"))
        g = hol(_key(k.get("product_id") or bez), bez)
        g.einkauf_anzahl += 1
        g.einkauf_summe += preis
        g.quellen.add(str(k.get("quelle") or "?"))
        ek_ges += preis
        ek_n += 1

    vk_ges = Decimal("0")
    vk_n = 0
    for s in verkaeufe:
        bez = str(getattr(s, "product_name", "") or getattr(s, "product_id", "")
                  or (s.get("title") if isinstance(s, dict) else "") or "unbekannt")
        brutto = Decimal(str(getattr(s, "brutto", None)
                             if not isinstance(s, dict) else s.get("gross", "0")))
        pid = (getattr(s, "product_id", None) if not isinstance(s, dict)
               else s.get("product_id"))
        g = hol(_key(pid or bez), bez)
        g.verkauf_anzahl += 1
        g.verkauf_summe += brutto
        g.quellen.add("verkauf")
        vk_ges += brutto
        vk_n += 1

    for g in gruppen.values():
        g.einkauf_summe = _q(g.einkauf_summe)
        g.verkauf_summe = _q(g.verkauf_summe)

    return Warenbuch(gruppen=gruppen, einkauf_gesamt=_q(ek_ges),
                     verkauf_gesamt=_q(vk_ges), einkauf_anzahl=ek_n, verkauf_anzahl=vk_n)


def render_bestand_text(w: Warenbuch, *, top: int = 20) -> str:
    z = ["📦 Warenbuch / Bestand", "=" * 40]
    z.append(f"Käufe:    {w.einkauf_anzahl} Stk · {w.einkauf_gesamt} EUR")
    z.append(f"Verkäufe: {w.verkauf_anzahl} Stk · {w.verkauf_gesamt} EUR")
    z.append(f"Bestand (gekauft − verkauft): {w.bestand_anzahl} Stk")
    z.append(f"Roh-Marge (Verkauf − Einkauf): {w.roh_marge} EUR")
    im_bestand = [g for g in w.gruppen.values() if g.bestand > 0]
    if im_bestand:
        z.append("")
        z.append(f"Noch im Bestand (Top {top}):")
        for g in sorted(im_bestand, key=lambda x: x.einkauf_summe, reverse=True)[:top]:
            z.append(f"  {g.bestand}× {g.bezeichnung[:38]}  (EK {g.einkauf_summe} EUR)")
    return "\n".join(z)


def schreibe_warenbuch_json(pfad: str, w: Warenbuch) -> None:
    os.makedirs(os.path.dirname(pfad) or ".", exist_ok=True)
    daten = {
        "einkauf_gesamt": str(w.einkauf_gesamt), "verkauf_gesamt": str(w.verkauf_gesamt),
        "einkauf_anzahl": w.einkauf_anzahl, "verkauf_anzahl": w.verkauf_anzahl,
        "bestand_anzahl": w.bestand_anzahl, "roh_marge": str(w.roh_marge),
        "gruppen": [
            {"bezeichnung": g.bezeichnung, "einkauf_anzahl": g.einkauf_anzahl,
             "einkauf_summe": str(g.einkauf_summe), "verkauf_anzahl": g.verkauf_anzahl,
             "verkauf_summe": str(g.verkauf_summe), "bestand": g.bestand,
             "marge": str(g.marge), "quellen": sorted(g.quellen)}
            for g in sorted(w.gruppen.values(), key=lambda x: x.einkauf_summe, reverse=True)
        ],
    }
    with open(pfad, "w", encoding="utf-8") as fh:
        json.dump(daten, fh, ensure_ascii=False, indent=2)
