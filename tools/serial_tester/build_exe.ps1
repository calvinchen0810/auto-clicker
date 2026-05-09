$ErrorActionPreference = 'Stop'

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectDir

$python = 'C:/Users/chencal/AppData/Local/Microsoft/WindowsApps/python3.11.exe'

& $python -m pip install -r requirements.txt
& $python -m PyInstaller --noconfirm --clean --onefile --windowed --name serial_tester serial_tester.py

Write-Host "Build complete: $projectDir/dist/serial_tester.exe"
