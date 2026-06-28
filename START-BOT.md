# Bot auf dem eigenen PC starten (Schnellstart)

Ziel: Der Telegram-Bot antwortet auf deine Nachrichten. Dauert ~10 Minuten.

## 0. Einmalig: Python installieren (falls noch nicht da)
- **Windows:** https://www.python.org/downloads/ → „Download" → beim Installieren
  unbedingt **„Add Python to PATH"** anhaken.
- **Mac:** Python 3 ist meist da; sonst `brew install python` oder von python.org.

Prüfen (Terminal / Eingabeaufforderung öffnen):
```
python --version
```
(Falls „nicht gefunden": auf dem Mac `python3` statt `python` benutzen.)

## 1. Projekt auf den PC holen
```
git clone -b claude/de-tax-accounting-agent-v2-beghts <REPO-URL> sero-agent
cd sero-agent
```
(REPO-URL = die Adresse deines Repositories. Wenn du kein Git hast: auf der
Repo-Seite „Code → Download ZIP", entpacken, Ordner öffnen.)

## 2. Benötigtes Paket installieren
```
pip install pyyaml
```
(Nur das wird für den Bot gebraucht. Optional für /duden-KI-Antworten: `pip install anthropic`.)

## 3. Konfiguration anlegen
```
copy config.example.yaml config.yaml      # Windows
cp   config.example.yaml config.yaml      # Mac/Linux
```
Dann `config.yaml` in einem Editor öffnen und beim Telegram-Bereich den **Token**
eintragen (von BotFather):
```yaml
interface:
  telegram:
    token: "DEIN_TELEGRAM_TOKEN"
    allowed_user_ids: []      # bleibt erst mal leer
```

## 4. Verbindung testen
```
python run.py telegram-check
```
→ Muss zeigen: `Bot OK: @Steuerboardbackboardbot`
(Fehler? Dann stimmt der Token nicht oder kein Internet.)

## 5. Bot starten
```
python run.py telegram
```
Das Fenster bleibt offen — **solange es läuft, ist der Bot online.**

## 6. Dich freischalten
1. Schreib dem Bot in Telegram irgendwas (z. B. `hallo`).
2. Er antwortet: **„Nicht autorisiert. Deine User-ID: 123456789"**.
3. Diese Zahl in `config.yaml` eintragen:
   ```yaml
       allowed_user_ids: [123456789]
   ```
4. Im Terminal `Strg + C` (Bot stoppen), dann wieder `python run.py telegram`.
5. Jetzt `/uebersicht` an den Bot schicken → er antwortet richtig. 🎉

## Wichtig
- **Der Bot antwortet nur, solange `python run.py telegram` läuft.** Schließt du das
  Fenster, ist er offline. Für Dauerbetrieb (24/7) siehe `deploy/README.md` (Docker).
- Echte Zahlen im `/report` erscheinen erst, wenn du Belege + Kontoumsätze einspeist
  und einmal `python run.py sync ...` läufst (siehe Haupt-`README.md`).
