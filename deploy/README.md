# Remote-/Dauerbetrieb

Der Agent läuft autonom auf einem Server — du legst nur Belege und den
Kontoumsatz-Export ab, alles andere passiert im Takt. **Live-Zugriff auf
eBay/Lexware/Telegram braucht deine Credentials in `config.yaml`** (gitignored) und
einen Server mit ausgehendem Internetzugang.

## Was wann läuft

`python run.py serve` startet:
1. den **Telegram-Bot** (Review/Freigabe + `/duden`) in einem Thread, und
2. die **Pipeline** (`run-all`) im konfigurierten Takt (`betrieb.pipeline_intervall_stunden`).

`run-all` führt jeden Schritt nur aus, wenn seine Voraussetzungen erfüllt sind
(robust — ein fehlender Schritt bricht den Lauf nicht ab):
- `ebay-kaeufe-api` → neue Käufe der letzten ~90 Tage live holen (mergen), falls ein
  eBay-Token (`refresh_token` oder `access_token`) gesetzt ist
- `ebay-kaeufe` → Einkaufspreise, falls `pfade.ebay_kaeufe_export` existiert
- `ebay-sync` → Verkäufe + Auszahlungen, falls eBay-`ru_name` + `refresh_token` gesetzt
- `sync` → Reconciliation + Payout-Abgleich + §25a + USt-VA + EÜR + Schwellen, falls
  `pfade.belege_inbox` (Ordner) und `pfade.bank_csv` vorhanden

## Variante A — Docker (empfohlen)

```bash
cp config.example.yaml config.yaml      # Secrets eintragen
mkdir -p deploy/inbox/belege            # Belege hier ablegen; Konto-CSV nach deploy/inbox/
docker compose -f deploy/docker-compose.yml up -d
docker compose -f deploy/docker-compose.yml logs -f
```

`config.yaml` und die Daten-Volumes werden eingehängt, **nicht** ins Image gebacken.
Der Healthcheck prüft stündlich die Audit-Hashkette.

## Variante B — systemd (ohne Docker)

```bash
sudo mkdir -p /opt/sero-agent && sudo chown $USER /opt/sero-agent
git clone <repo> /opt/sero-agent && cd /opt/sero-agent
python -m venv .venv && .venv/bin/pip install -r requirements.txt anthropic
cp config.example.yaml config.yaml      # Secrets eintragen
sudo cp deploy/sero-agent.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now sero-agent
journalctl -u sero-agent -f
```

## Variante C — Cron (Pipeline getaktet, Bot separat)

Siehe [`crontab.example`](crontab.example): `run-all` alle 6 h, tägliche
Audit-Prüfung, Bot via `@reboot` oder systemd.

## Einmalige Vorbereitung (von dir, im Browser)

Diese Schritte kann nur der Konto-Inhaber ausführen — sie sind **nicht**
automatisierbar:
1. **eBay-OAuth:** `python run.py ebay-auth` → URL im Browser bestätigen →
   `python run.py ebay-token <code>` → Refresh-Token in `config.yaml`.
2. **eBay-RuName** im Developer Portal hinterlegen.
3. **Lexware-Kategorie-UUIDs** (`/posting-categories`) in `kategorie_map`.
4. **eBay-Kaufhistorie** als JSON exportieren → `data/ebay_kaeufe.json`.
5. **Telegram-User-ID** in `allowed_user_ids` (Bot anschreiben, er nennt die ID).

## Sicherheit

- `config.yaml` enthält Live-Secrets → niemals committen (steht in `.gitignore`),
  read-only mounten, Dateirechte `600`.
- Geteilte/abgelegte API-Keys regelmäßig **rotieren**.
- Audit-Log + Belegspeicher liegen in persistenten Volumes (GoBD-Aufbewahrung).
- Der Agent bucht nichts verbindlich: Festschreibung/USt-VA bleiben
  freigabepflichtig (Human-in-the-Loop über Telegram).
