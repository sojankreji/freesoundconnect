# Build a distributable .exe with PyInstaller (Windows).
# Usage:  pip install -r requirements.txt pyinstaller ; .\scripts\build.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

pyinstaller --noconfirm --clean --onefile --windowed `
  --name FreesoundConnect `
  --icon assets\icon.ico `
  --add-data "assets\icon.png;assets" `
  freesound_connect.py

Write-Host ""
Write-Host "Built: dist\FreesoundConnect.exe"
