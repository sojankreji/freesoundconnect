#!/usr/bin/env bash
# Build a distributable executable with PyInstaller (macOS / Linux).
# Usage:  pip3 install -r requirements.txt pyinstaller && ./scripts/build.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [[ "$(uname -s)" == "Darwin" ]]; then
  pyinstaller --noconfirm --clean --windowed \
    --name "Freesound Connect" \
    --icon assets/icon.icns \
    --add-data "assets/icon.png:assets" \
    freesound_connect.py
  echo
  echo "Built: dist/Freesound Connect.app"
  echo "Zip for distribution:  ditto -c -k --keepParent 'dist/Freesound Connect.app' dist/FreesoundConnect-macOS.zip"
else
  pyinstaller --noconfirm --clean --onefile --windowed \
    --name freesound-connect \
    --add-data "assets/icon.png:assets" \
    freesound_connect.py
  echo
  echo "Built: dist/freesound-connect"
fi
