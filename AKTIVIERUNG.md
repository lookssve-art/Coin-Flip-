# Aktivierung — heute Abend (Reihenfolge einhalten)

Alles im Projektordner `~/Desktop/sero-agent`. Nach dem Audit ist der Bot-Start
gefixt (startet jetzt auch ohne vor­eingetragene ID — der erste Schreiber im Chat
wird automatisch Eigentümer).

## 1. Aktuellen Stand holen + PyYAML sichern
```bash
cd ~/Desktop/sero-agent
git pull
command -v python3                 # merke dir DIESEN Pfad (nimmt auch der Autostart)
python3 -c "import yaml && print('yaml ok')" || python3 -m pip install pyyaml
```

## 2. eBay-Dauerzugang herstellen (PFLICHT — der 2h-Token ist abgelaufen)
Trag in `config.yaml` unter `integrationen.ebay` deinen **RuName** ein (aus dem
eBay Developer Portal, Feld „Your auth accepted URL / RuName"). Dann:
```bash
python3 run.py ebay-auth                 # Link öffnen, im Browser bestätigen
python3 run.py ebay-token <code>         # code aus der Redirect-URL — speichert refresh_token
```
Danach hält der Zugang dauerhaft (~18 Monate), kein 2h-Ablauf mehr.

## 3. Rechnungs-Absender setzen (sonst sind Rechnungen nicht §14-konform)
```bash
python3 run.py rechnung-setup "Dein Name" "Straße Nr." "PLZ" "Ort"
# Steuernummer später nachtragen:  python3 run.py rechnung-setup "" "" "" "" "DEINE-STEUERNR"
```

## 4. Gegenprobe
```bash
python3 run.py check
```
Erwartung: eBay-Refresh-Token ✓, Absenderdaten ✓, Lexware/Telegram/Claude ✓.
(kategorie_map + Konto-CSV dürfen offen bleiben — für den Kernlauf nicht nötig.)

## 5. Autostart einrichten (einmalig)
```bash
bash deploy/install-macos.sh
launchctl list | grep com.sero.agent      # läuft?
```
Der Bot läuft ab jetzt automatisch (auch nach Neustart). Logs:
`log/serve.out.log` / `log/serve.err.log`.

## 6. Über Telegram testen
Dem Bot **„hi"** schreiben → du wirst als Eigentümer freigeschaltet. Dann:
```
/uebersicht      → muss antworten
/buchhaltung     → kompletter Lauf, ~1–2 Min, dann Schluss-Übersicht mit echten Zahlen
```
Zeigt die Übersicht 0,00 EUR → eBay-Token nicht gültig → zurück zu Schritt 2.

---

## Wichtig zu wissen (aus dem Steuer-Audit)

- **§13b Reverse-Charge:** Auf die eBay-Gebühren schuldest du 19 % USt selbst ans
  Finanzamt — **auch als Kleinunternehmer**. Der Agent rechnet das jetzt aus, bucht
  es als Kosten und meldet es dir. **Du brauchst dafür eine USt-IdNr (BZSt) und musst
  eine USt-VA (Kz 46/47) abgeben.** Bitte einmal mit dem Steuerberater bestätigen.
- **25.000-€-Grenze (Gründungsjahr):** Der Agent warnt dich per Telegram, bevor du
  sie reißt. Beim Überschreiten kippt der Kleinunternehmer-Status.
- Der Agent finalisiert in Lexware **nie automatisch** — alles bleibt Entwurf bis zu
  deiner Freigabe.

Dieser Setup ersetzt keinen Steuerberater. §13b-USt-IdNr und die KU-Grenze einmalig
mit dem StB klären.
