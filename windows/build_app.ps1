param(
    [string]$Python = "py -3.12"
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    & cmd.exe /c "$Python -m venv .venv"
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Windows virtual environment.' }
}
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r requirements-app.txt pyinstaller==6.16.0
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }

New-Item -ItemType Directory -Force runtime | Out-Null
& $VenvPython setup_patricia.py
if ($LASTEXITCODE -ne 0) { throw 'Patricia installation failed.' }

& $VenvPython -m PyInstaller --noconfirm --clean windows\MoveCoachApp.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller app build failed.' }

$env:QT_QPA_PLATFORM = 'offscreen'
& (Join-Path $Root 'dist\MoveCoachApp\MoveCoach.exe') --smoke
if ($LASTEXITCODE -ne 0) { throw 'Move Coach app smoke test failed.' }
Write-Host 'Created dist\MoveCoachApp\MoveCoach.exe (smoke OK)'
