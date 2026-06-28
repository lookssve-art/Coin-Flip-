@echo off
REM === SERO Steuer-Agent: Telegram-Bot starten (Windows, Doppelklick) ===
cd /d "%~dp0"

echo Installiere benoetigtes Paket...
pip install pyyaml >nul 2>&1

if not exist config.yaml (
  copy config.example.yaml config.yaml >nul
  echo.
  echo  >>> WICHTIG: Oeffne jetzt die Datei  config.yaml  in einem Editor,
  echo  >>> trage bei  interface: telegram: token:  deinen Telegram-Token ein,
  echo  >>> speichere, und starte diese Datei erneut.
  echo.
  pause
  exit /b
)

echo Pruefe Telegram-Verbindung...
python run.py telegram-check
if errorlevel 1 (
  echo.
  echo  >>> Token-Pruefung fehlgeschlagen. Bitte Token in config.yaml pruefen.
  pause
  exit /b
)

echo.
echo  Bot laeuft. Schreib ihm in Telegram eine Nachricht -- der erste Schreiber
echo  wird automatisch freigeschaltet. Dieses Fenster offen lassen!
echo  (Beenden mit Strg+C)
echo.
python run.py telegram
pause
