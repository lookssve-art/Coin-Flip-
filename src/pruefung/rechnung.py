"""Selbst-Prüfung einer Rechnung vor dem Verschicken/Buchen (§14 / §33 UStDV).

Der Agent hinterfragt jede Rechnung: Sind ALLE Pflichtangaben da (Absender inkl.
Steuernummer/USt-IdNr, Empfänger, fortlaufende Nummer, Rechnungs- + Leistungs-
datum, Positionen, Beträge, §19-Hinweis)? Stimmt die Rechnung rechnerisch?
Erst wenn KEIN Fehler übrig bleibt, ist sie ``versandfertig`` — sonst geht sie in
die Review-Queue statt raus.
"""

from __future__ import annotations

from decimal import Decimal

from .checks import Befund, Schwere

# Kleinbetragsrechnung (§33 UStDV): bis 250 EUR brutto reduzierte Pflichtangaben.
KLEINBETRAG_GRENZE = Decimal("250")


def pruefe_rechnung(r, *, kleinunternehmer: bool = True) -> list[Befund]:
    """Prüft eine ``Rechnung`` gegen die Pflichtangaben. Liefert alle Befunde."""
    b: list[Befund] = []
    a = getattr(r, "absender", None)
    summe = _dec(getattr(r, "summe", 0))
    kleinbetrag = summe <= KLEINBETRAG_GRENZE

    # --- Absender (immer Pflicht) ---
    if not a or not getattr(a, "name", ""):
        b.append(Befund("absender.name", Schwere.FEHLER, "Absender-Name fehlt."))
    if not a or not (getattr(a, "strasse", "") and getattr(a, "plz", "") and getattr(a, "ort", "")):
        b.append(Befund("absender.anschrift", Schwere.FEHLER, "Absender-Anschrift unvollständig."))
    if not a or not (getattr(a, "steuernummer", "") or getattr(a, "ust_id", "")):
        b.append(Befund("absender.steuernummer", Schwere.FEHLER,
                        "Steuernummer ODER USt-IdNr fehlt (§14 Abs. 4 Nr. 2)."))
    else:
        # 11 Ziffern am Stueck = persoenliche Steuer-ID (IdNr) — nicht §14-tauglich.
        import re
        stnr = str(getattr(a, "steuernummer", "") or "").replace(" ", "")
        if re.fullmatch(r"\d{11}", stnr):
            b.append(Befund("absender.steuernummer", Schwere.FEHLER,
                            "Das sieht wie die persoenliche Steuer-ID aus (11 Ziffern) — "
                            "auf Rechnungen gehoert die FA-Steuernummer (1xx/xxx/xxxxx) "
                            "oder USt-IdNr (§14 Abs. 4 Nr. 2)."))

    # --- Rechnungsnummer + Daten ---
    if not getattr(r, "nummer", ""):
        b.append(Befund("nummer", Schwere.FEHLER, "Fortlaufende Rechnungsnummer fehlt."))
    if not getattr(r, "datum", None):
        b.append(Befund("datum", Schwere.FEHLER, "Rechnungsdatum fehlt."))
    if not (getattr(r, "leistungsdatum", None) or getattr(r, "datum", None)):
        b.append(Befund("leistungsdatum", Schwere.FEHLER, "Leistungsdatum fehlt."))

    # --- Empfänger (bei > 250 EUR Pflicht) ---
    e = getattr(r, "empfaenger", None)
    e_name = (getattr(e, "name", "") if e else "")
    if not kleinbetrag and not e_name:
        b.append(Befund("empfaenger.name", Schwere.FEHLER,
                        "Empfängername fehlt (Pflicht ab 250 EUR, §14 Abs. 4 Nr. 1)."))
    if not kleinbetrag and e and not (getattr(e, "strasse", "") and getattr(e, "ort", "")):
        b.append(Befund("empfaenger.anschrift", Schwere.HINWEIS,
                        "Empfänger-Anschrift unvollständig (ab 250 EUR empfohlen/Pflicht)."))

    # --- Positionen + Rechnerische Prüfung ---
    positionen = list(getattr(r, "positionen", []) or [])
    if not positionen:
        b.append(Befund("positionen", Schwere.FEHLER, "Keine Rechnungsposition vorhanden."))
    pos_summe = Decimal("0")
    for i, p in enumerate(positionen, start=1):
        if not getattr(p, "bezeichnung", ""):
            b.append(Befund(f"pos{i}.bezeichnung", Schwere.FEHLER, f"Position {i}: Bezeichnung fehlt."))
        menge = _dec(getattr(p, "menge", 0))
        if menge <= 0:
            b.append(Befund(f"pos{i}.menge", Schwere.FEHLER, f"Position {i}: Menge <= 0."))
        gesamt = _dec(getattr(p, "gesamt", 0))
        erwartet = (menge * _dec(getattr(p, "einzelpreis", 0))).quantize(Decimal("0.01"))
        if gesamt != erwartet:
            b.append(Befund(f"pos{i}.rechnung", Schwere.FEHLER,
                            f"Position {i}: Menge×Einzelpreis ({erwartet}) ≠ Gesamt ({gesamt})."))
        pos_summe += gesamt

    if summe <= 0:
        b.append(Befund("summe", Schwere.FEHLER, "Rechnungssumme ist 0 oder negativ."))
    elif pos_summe.quantize(Decimal("0.01")) != summe.quantize(Decimal("0.01")):
        b.append(Befund("summe", Schwere.FEHLER,
                        f"Summe der Positionen ({pos_summe}) ≠ Rechnungssumme ({summe})."))

    # --- Kleinunternehmer-Pflichthinweis ---
    if kleinunternehmer and not getattr(r, "kleinunternehmer_hinweis", ""):
        b.append(Befund("kleinunternehmer_hinweis", Schwere.FEHLER,
                        "§19-Pflichthinweis fehlt (keine USt / Kleinunternehmer)."))

    if not b:
        b.append(Befund("rechnung", Schwere.OK, "Alle Pflichtangaben vorhanden, rechnerisch stimmig."))
    return b


def versandfertig(r, *, kleinunternehmer: bool = True) -> tuple[bool, list[Befund]]:
    """True + Befunde, wenn KEIN Fehler übrig ist (dann darf raus/gebucht werden)."""
    befunde = pruefe_rechnung(r, kleinunternehmer=kleinunternehmer)
    ok = not any(x.schwere == Schwere.FEHLER for x in befunde)
    return ok, befunde


def fehler_texte(befunde: list[Befund]) -> list[str]:
    return [x.nachricht for x in befunde if x.schwere == Schwere.FEHLER]


def _dec(v) -> Decimal:
    try:
        return Decimal(str(v))
    except Exception:  # noqa: BLE001
        return Decimal("0")
