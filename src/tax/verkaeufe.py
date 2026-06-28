"""Verkaufs-Journalisierung: § 25a-Marge je Artikel + USt je Satz (Regelware).

Verarbeitet ``PlatformSale``s (z. B. aus dem eBay-Import) zu:
  * Differenzbesteuerungs-Eintraegen (§ 25a) je Artikel — Marge = Verkauf − Einkauf,
  * USt je Satz fuer regelbesteuerte Verkaeufe,
  * der aus § 25a-Margen herausgerechneten USt-Summe.

Wichtige Compliance-Regeln (Abschnitt 2.5 / 5.4 der Spezifikation):
  * § 25a erfordert den **Einkaufspreis je Artikel**; fehlt er, geht der Vorgang in
    die Review (kein Raten).
  * Von eBay als Deemed Supplier bereits abgefuehrte USt (``ebay_collected_vat``)
    wird NICHT erneut angesetzt (Doppelversteuerung vermeiden).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

from ..models import PlatformSale, TaxScheme
from ..util.datum import ist_eu_b2c_fernverkauf
from .differenzbesteuerung import einzeldifferenz, MargenErgebnis

_CENT = Decimal("0.01")


@dataclass
class VerkaufsJournal:
    differenz_eintraege: list = field(default_factory=list)   # [(artikel_id, MargenErgebnis)]
    differenz_ust: Decimal = Decimal("0")
    regel_ust_je_satz: dict = field(default_factory=dict)     # {"19": Decimal, ...}
    deemed_supplier_ust: Decimal = Decimal("0")               # von eBay abgefuehrt (Info)
    review_ids: list = field(default_factory=list)            # Verkaeufe ohne Einkaufspreis
    umsatz_brutto: Decimal = Decimal("0")                     # Gesamt-Bruttoumsatz (§19-Monitoring)
    oss_netto_eu_b2c: Decimal = Decimal("0")                  # EU-B2C netto OHNE §25a (OSS-Schwelle)


def _round(v: Decimal) -> Decimal:
    return Decimal(v).quantize(_CENT, rounding=ROUND_HALF_UP)


def journalisiere_verkaeufe(
    sales: list[PlatformSale],
    einkaufspreise: dict[str, Decimal],
    *,
    default_ust_satz: Decimal = Decimal("19"),
) -> VerkaufsJournal:
    """Erzeugt das Verkaufs-Journal aus Plattform-Verkaeufen + Einkaufspreis-Map."""
    j = VerkaufsJournal()
    for s in sales:
        # Refunds/Null-Vorgaenge tragen keine eigene Ausgangs-USt.
        verkauf = Decimal(s.brutto)
        if verkauf <= 0:
            continue
        j.umsatz_brutto += verkauf

        # Deemed Supplier: eBay hat USt bereits abgefuehrt -> nicht erneut ansetzen.
        if Decimal(s.ebay_collected_vat) > 0:
            j.deemed_supplier_ust += Decimal(s.ebay_collected_vat)
            continue

        if s.tax_scheme == TaxScheme.DIFFERENZ:
            einkauf = einkaufspreise.get(s.product_id or "")
            if einkauf is None:
                j.review_ids.append(s.id)   # Einkaufsbeleg unklar -> Review
                continue
            marge = einzeldifferenz(verkauf, Decimal(einkauf), default_ust_satz)
            j.differenz_eintraege.append((s.product_id or s.id, marge))
            j.differenz_ust += marge.ust_betrag
            # § 25a-Ware ist aus der OSS-Schwelle ausdruecklich ausgenommen.
        else:
            satz = default_ust_satz
            faktor = Decimal("1") + satz / Decimal("100")
            netto = _round(verkauf / faktor)
            ust = _round(verkauf - netto)
            key = str(satz)
            j.regel_ust_je_satz[key] = j.regel_ust_je_satz.get(key, Decimal("0")) + ust
            # EU-B2C-Fernverkauf (Regelware) zaehlt zur 10.000-EUR-OSS-Schwelle.
            if not s.customer_is_business and ist_eu_b2c_fernverkauf(s.customer_country):
                j.oss_netto_eu_b2c += netto

    j.differenz_ust = _round(j.differenz_ust)
    j.regel_ust_je_satz = {k: _round(v) for k, v in j.regel_ust_je_satz.items()}
    j.deemed_supplier_ust = _round(j.deemed_supplier_ust)
    j.umsatz_brutto = _round(j.umsatz_brutto)
    j.oss_netto_eu_b2c = _round(j.oss_netto_eu_b2c)
    return j
