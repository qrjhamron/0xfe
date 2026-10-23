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

# The exe is useless without the WebEngine runtime next to it; verify the
# bundle actually contains it instead of trusting hidden-import warnings.
$BundleQt = Join-Path $Root 'dist\MoveCoachApp\_internal\PySide6'
foreach ($Name in 'QtWebEngineCore.pyd', 'QtWebEngineWidgets.pyd',
         'QtWebEngineProcess.exe', 'Qt6WebEngineCore.dll') {
    if (-not (Test-Path (Join-Path $BundleQt $Name))) {
        throw "Bundled QtWebEngine file missing: $Name"
    }
}

if (-not (Test-Path (Join-Path $Root 'dist\MoveCoachApp\MoveCoachPanel.exe'))) {
    throw 'Bundled panel app missing: MoveCoachPanel.exe'
}

$env:QT_QPA_PLATFORM = 'offscreen'
# Start-Process -Wait: a plain `&` call does not wait for a GUI-subsystem
# exe, so $LASTEXITCODE never reflected the smoke result.
$Smoke = Start-Process -FilePath (Join-Path $Root 'dist\MoveCoachApp\MoveCoach.exe') `
    -ArgumentList '--smoke' -Wait -PassThru
if ($Smoke.ExitCode -ne 0) { throw "Move Coach app smoke test failed (exit $($Smoke.ExitCode))." }
$PanelSmoke = Start-Process -FilePath (Join-Path $Root 'dist\MoveCoachApp\MoveCoachPanel.exe') `
    -ArgumentList '--smoke' -Wait -PassThru
if ($PanelSmoke.ExitCode -ne 0) { throw "Move Coach panel smoke test failed (exit $($PanelSmoke.ExitCode))." }
Write-Host 'Created dist\MoveCoachApp\MoveCoach.exe (smoke OK)'
