param(
    [switch]$Clean,
    [switch]$InstallChromium,
    [string]$Python = "py -3.12"
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root

function Invoke-Python([string[]]$Arguments) {
    & cmd.exe /c "$Python $($Arguments -join ' ')"
    if ($LASTEXITCODE -ne 0) { throw "Python command failed with exit code $LASTEXITCODE" }
}

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    & cmd.exe /c "$Python -m venv .venv"
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Windows virtual environment.' }
}
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r requirements.txt pyinstaller==6.16.0
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }

# Patricia-focused build: no Lc0 binaries/weights and no Maia checkpoint
# are downloaded or packaged. Lc0/Maia modes remain available only in
# source installs that provide those engines themselves.
New-Item -ItemType Directory -Force runtime | Out-Null
if (-not (Test-Path 'runtime\patricia.exe')) {
    $PatriciaUrl = 'https://github.com/Adam-Kulju/Patricia/releases/download/5.1/patricia_v2.exe'
    $PatriciaSha256 = '5B3E90932771C218BABF2C12EA55AF8389F7BEF1E5FC6C391D9415F86B4FFF51'
    Invoke-WebRequest -Uri $PatriciaUrl -OutFile 'runtime\patricia.exe'
    if ((Get-FileHash 'runtime\patricia.exe' -Algorithm SHA256).Hash -ne $PatriciaSha256) {
        throw 'Patricia checksum mismatch.'
    }
}
if ($InstallChromium) {
    & $VenvPython -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw 'Chromium installation failed.' }
}

if ($Clean) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build, dist, windows\Output
}
& $VenvPython -m PyInstaller --noconfirm --clean windows\MoveCoach.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

$Iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source
if (-not $Iscc) {
    $Candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
    )
    $Iscc = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $Iscc) {
    throw 'Inno Setup compiler (iscc.exe) is required to create the final Setup.exe.'
}
New-Item -ItemType Directory -Force windows\Output | Out-Null
& $Iscc /Qp windows\MoveCoach.iss
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup build failed.' }
Write-Host "Created windows\Output\MoveCoach-Setup-v15.exe"
