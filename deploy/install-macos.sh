#!/bin/bash
# SERO-Agent Autostart fuer macOS (launchd).
# EINMAL ausfuehren:  bash deploy/install-macos.sh
# Danach startet der Bot automatisch mit dem Mac (auch nach Neustart) und
# laeuft dauerhaft im Hintergrund — kein Terminal mehr noetig.
#
# Deinstallieren:     bash deploy/install-macos.sh --uninstall

set -e

LABEL="com.sero.agent"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"

# Projektverzeichnis = Ordner ueber diesem Skript (…/sero-agent).
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$(command -v python3 || echo /usr/bin/python3)"
LOG_DIR="$PROJECT_DIR/log"

if [ "$1" = "--uninstall" ]; then
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "✅ Autostart entfernt. Der Bot startet nicht mehr automatisch."
  exit 0
fi

# Vorpruefung: config.yaml vorhanden?
if [ ! -f "$PROJECT_DIR/config.yaml" ]; then
  echo "⚠ Keine config.yaml in $PROJECT_DIR gefunden — bitte zuerst einrichten."
  exit 1
fi

# Kritisch: PyYAML MUSS fuer genau den python3 da sein, den launchd startet —
# sonst laedt der Agent still eine leere Config (Bot/eBay/Lexware inaktiv).
if ! "$PYTHON" -c "import yaml" 2>/dev/null; then
  echo "⚠ '$PYTHON' hat kein PyYAML — der Autostart liefe sonst OHNE deine config.yaml!"
  echo "  Fix:  $PYTHON -m pip install pyyaml"
  echo "  (Danach dieses Skript erneut ausfuehren.)"
  exit 1
fi

mkdir -p "$LOG_DIR" "$HOME/Library/LaunchAgents"

# launchd-Plist schreiben (mit echten Pfaden).
cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON}</string>
    <string>run.py</string>
    <string>serve</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${PROJECT_DIR}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/serve.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/serve.err.log</string>
  <key>ThrottleInterval</key>
  <integer>30</integer>
</dict>
</plist>
PLISTEOF

# Neu laden (erst entladen, falls schon aktiv).
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "✅ Autostart eingerichtet!"
echo "   Bot laeuft ab jetzt automatisch (auch nach Neustart) — kein Terminal noetig."
echo "   Projekt: $PROJECT_DIR"
echo "   Python:  $PYTHON"
echo "   Logs:    $LOG_DIR/serve.out.log  (und serve.err.log)"
echo ""
echo "Naechster Schritt: Schreib deinem Telegram-Bot 'hi' und tippe /buchhaltung."
echo "Status pruefen:  launchctl list | grep ${LABEL}"
echo "Stoppen:         bash deploy/install-macos.sh --uninstall"
