$ErrorActionPreference = 'Stop'

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectDir

$python = 'C:/Users/chencal/AppData/Local/Microsoft/WindowsApps/python3.11.exe'

& $python -m pip install -r requirements.txt
& $python build.py --clean

Write-Host "Build complete: $projectDir/dist/ServoServer.exe"
