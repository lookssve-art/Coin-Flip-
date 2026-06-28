#!/usr/bin/env bash
# === SERO Steuer-Agent: Telegram-Bot starten (Mac/Linux) ===
# Ausfuehren:  bash start-bot.sh
cd "$(dirname "$0")" || exit 1

PY=python3
command -v $PY >/dev/null 2>&1 || PY=python

echo "Installiere benoetigtes Paket..."
$PY -m pip install --quiet pyyaml 2>/dev/null || pip install --quiet pyyaml

if [ ! -f config.yaml ]; then
  cp config.example.yaml config.yaml
  echo
  echo "  >>> WICHTIG: Oeffne jetzt  config.yaml  in einem Editor,"
  echo "  >>> trage bei  interface: telegram: token:  deinen Telegram-Token ein,"
  echo "  >>> speichere, und starte dieses Skript erneut (bash start-bot.sh)."
  echo
  exit 0
fi

echo "Pruefe Telegram-Verbindung..."
if ! $PY run.py telegram-check; then
  echo
  echo "  >>> Token-Pruefung fehlgeschlagen. Bitte Token in config.yaml pruefen."
  exit 1
fi

echo
echo "  Bot laeuft. Schreib ihm in Telegram eine Nachricht -- der erste Schreiber"
echo "  wird automatisch freigeschaltet. Dieses Fenster offen lassen!"
echo "  (Beenden mit Strg+C)"
echo
$PY run.py telegram
