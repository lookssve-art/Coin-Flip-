"""Rechnung aus einem ``PlatformSale`` bauen und als HTML/Text rendern.

Kleinunternehmer (§19): Brutto = Netto, keine USt, Pflicht-Hinweis. Der
Empfaenger kommt aus den eBay-Daten, soweit vorhanden, sonst ein neutraler
Platzhalter (B2C-Verkauf ohne uebermittelte Anschrift).
"""

from __future__ import annotations

import html
from datetime import date
from decimal import Decimal

from .modell import Absender, Empfaenger, Position, Rechnung


def rechnung_aus_verkauf(sale, *, nummer: str, absender: Absender,
                         kleinunternehmer: bool = True,
                         hinweis: str | None = None) -> Rechnung:
    """Erzeugt eine ``Rechnung`` aus einem ``PlatformSale``.

    ``sale`` braucht mindestens ``id``, ``datum``, ``brutto``; optionale Felder
    ``product_id``, ``customer_name``, ``customer_country`` werden genutzt.
    """
    # Bezeichnung: Artikeltitel bevorzugen, sonst SKU/ItemID, sonst Platzhalter.
    bezeichnung = (getattr(sale, "product_name", "") or getattr(sale, "product_id", None)
                   or "Artikel (eBay-Verkauf)")
    name = getattr(sale, "customer_name", "") or ""
    land = getattr(sale, "customer_country", "DE") or "DE"
    empf = Empfaenger(name=name, land=land,
                      strasse=getattr(sale, "customer_street", "") or "",
                      plz=getattr(sale, "customer_zip", "") or "",
                      ort=getattr(sale, "customer_city", "") or "")
    # Stueckzahl + Einzelpreis aus eBay; Einzelpreis sonst aus brutto/menge ableiten.
    brutto = Decimal(str(getattr(sale, "brutto", "0")))
    menge = Decimal(str(getattr(sale, "menge", "1") or "1"))
    if menge <= 0:
        menge = Decimal("1")
    einzel = Decimal(str(getattr(sale, "einzelpreis", "0") or "0"))
    if einzel > 0 and (einzel * menge).quantize(Decimal("0.01")) == brutto:
        # Exakter eBay-Einzelpreis: Menge x Einzel == Verkaufsbetrag.
        pos = Position(bezeichnung=str(bezeichnung), menge=menge, einzelpreis=einzel)
    elif menge > 1 and (brutto / menge).quantize(Decimal("0.01")) * menge == brutto:
        # Aus brutto/menge ableitbar OHNE Rundungsrest.
        pos = Position(bezeichnung=str(bezeichnung), menge=menge,
                       einzelpreis=(brutto / menge).quantize(Decimal("0.01")))
    else:
        # Nicht sauber teilbar (Rundungsrest) -> eine Sammelposition, damit die
        # Rechnungssumme IMMER dem tatsaechlichen Verkaufsbetrag entspricht.
        bez = str(bezeichnung) + (f" ({menge} Stk.)" if menge > 1 else "")
        pos = Position(bezeichnung=bez, menge=Decimal("1"), einzelpreis=brutto)
    r = Rechnung(
        nummer=nummer,
        datum=getattr(sale, "datum", date.today()),
        leistungsdatum=getattr(sale, "datum", None),
        empfaenger=empf,
        positionen=[pos],
        absender=absender,
        kleinunternehmer=kleinunternehmer,
        bestell_referenz=str(getattr(sale, "id", "")),
    )
    if hinweis:
        r.kleinunternehmer_hinweis = hinweis
    if not kleinunternehmer:
        r.kleinunternehmer_hinweis = ""
    return r


def render_text(r: Rechnung) -> str:
    """Schlichte, menschenlesbare Textfassung (Beleg/Archiv)."""
    a, e = r.absender, r.empfaenger
    zeilen = [
        f"{a.name}", f"{a.strasse}", f"{a.plz} {a.ort}", "",
        f"Rechnung {r.nummer}",
        f"Datum: {r.datum.isoformat()}   Leistungsdatum: {(r.leistungsdatum or r.datum).isoformat()}",
        "",
        f"Empfänger: {e.anzeige}" + (f", {e.land}" if e.land else ""),
        f"Bestell-Referenz: {r.bestell_referenz}" if r.bestell_referenz else "",
        "",
        f"{'Pos':<4}{'Bezeichnung':<40}{'Menge':>7}{'Einzel':>12}{'Gesamt':>12}",
    ]
    for i, p in enumerate(r.positionen, start=1):
        zeilen.append(f"{i:<4}{p.bezeichnung[:38]:<40}{str(p.menge):>7}"
                      f"{str(p.einzelpreis):>12}{str(p.gesamt):>12}")
    zeilen += [
        "", f"{'Gesamtbetrag:':>63}{str(r.summe):>12} EUR", "",
    ]
    if r.kleinunternehmer and r.kleinunternehmer_hinweis:
        zeilen.append(r.kleinunternehmer_hinweis)
    steuerinfo = (f"USt-IdNr: {a.ust_id}" if a.ust_id
                  else (f"Steuernummer: {a.steuernummer}" if a.steuernummer else ""))
    if steuerinfo:
        zeilen.append(steuerinfo)
    if a.iban:
        zeilen.append(f"Zahlbar auf IBAN {a.iban}" + (f" ({a.bic})" if a.bic else ""))
    return "\n".join(z for z in zeilen if z is not None)


def _logo_data_uri(pfad: str) -> str:
    """Bettet das Logo als data-URI ein (Rechnung bleibt self-contained/GoBD)."""
    if not pfad:
        return ""
    import base64
    import os
    if not os.path.exists(pfad):
        return ""
    endung = os.path.splitext(pfad)[1].lower()
    mime = {"jpg": "image/jpeg", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".svg": "image/svg+xml"}.get(endung, "image/png")
    with open(pfad, "rb") as fh:
        return f"data:{mime};base64," + base64.b64encode(fh.read()).decode("ascii")


def render_html(r: Rechnung, *, logo_pfad: str = "") -> str:
    """Druckbare HTML-Rechnung (kann im Browser als PDF gespeichert werden)."""
    a, e = r.absender, r.empfaenger
    esc = html.escape
    logo_uri = _logo_data_uri(logo_pfad)
    logo_html = (f'<div class="logo"><img src="{logo_uri}" alt="Logo"></div>'
                 if logo_uri else "")

    pos_rows = "".join(
        f"<tr><td>{i}</td><td>{esc(p.bezeichnung)}</td>"
        f"<td class='r'>{esc(str(p.menge))}</td>"
        f"<td class='r'>{esc(str(p.einzelpreis))} €</td>"
        f"<td class='r'>{esc(str(p.gesamt))} €</td></tr>"
        for i, p in enumerate(r.positionen, start=1)
    )
    steuerinfo = (f"USt-IdNr: {esc(a.ust_id)}" if a.ust_id
                  else (f"Steuernummer: {esc(a.steuernummer)}" if a.steuernummer else ""))
    bank = (f"<p>Zahlbar auf IBAN {esc(a.iban)}"
            + (f" ({esc(a.bic)})" if a.bic else "") + "</p>") if a.iban else ""
    hinweis = (f"<p class='hinweis'>{esc(r.kleinunternehmer_hinweis)}</p>"
               if r.kleinunternehmer and r.kleinunternehmer_hinweis else "")
    ref = (f"<p>Bestell-Referenz: {esc(r.bestell_referenz)}</p>"
           if r.bestell_referenz else "")
    empf_anschrift = "<br>".join(filter(None, [
        esc(e.anzeige), esc(e.strasse), esc(f"{e.plz} {e.ort}".strip()),
        esc(e.land) if e.land and e.land != "DE" else ""]))

    return f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><title>Rechnung {esc(r.nummer)}</title>
<style>
 body{{font-family:Arial,Helvetica,sans-serif;color:#1a1a1a;max-width:720px;margin:2em auto;font-size:14px}}
 .absender{{font-size:11px;color:#555;border-bottom:1px solid #ccc;padding-bottom:4px}}
 h1{{font-size:20px;margin:1.2em 0 .2em}}
 table{{width:100%;border-collapse:collapse;margin:1em 0}}
 th,td{{padding:6px 8px;border-bottom:1px solid #e0e0e0;text-align:left}}
 .r{{text-align:right}}
 tfoot td{{font-weight:bold;border-top:2px solid #333}}
 .hinweis{{background:#f6f6f6;padding:8px 10px;border-left:3px solid #888}}
 .meta{{color:#444}}
 .logo{{text-align:center;margin-bottom:1em}}
 .logo img{{max-width:160px;max-height:160px}}
</style></head><body>
{logo_html}
<div class="absender">{esc(a.name)} · {esc(a.strasse)} · {esc(a.plz)} {esc(a.ort)}</div>
<div style="margin-top:1.5em">{empf_anschrift}</div>
<h1>Rechnung {esc(r.nummer)}</h1>
<div class="meta">Rechnungsdatum: {r.datum.isoformat()} &nbsp;|&nbsp;
 Leistungsdatum: {(r.leistungsdatum or r.datum).isoformat()}</div>
{ref}
<table><thead><tr><th>Pos</th><th>Bezeichnung</th><th class="r">Menge</th>
 <th class="r">Einzelpreis</th><th class="r">Gesamt</th></tr></thead>
<tbody>{pos_rows}</tbody>
<tfoot><tr><td colspan="4" class="r">Gesamtbetrag</td>
 <td class="r">{esc(str(r.summe))} €</td></tr></tfoot></table>
{hinweis}
<p class="meta">{esc(a.name)}, {esc(a.strasse)}, {esc(a.plz)} {esc(a.ort)}<br>
 {steuerinfo}{(' · ' + esc(a.email)) if a.email else ''}{(' · ' + esc(a.telefon)) if a.telefon else ''}</p>
{bank}
</body></html>"""
