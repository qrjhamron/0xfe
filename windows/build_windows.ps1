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

if (-not (Test-Path 'runtime\stockfish.exe')) {
    & $VenvPython install.py --skip-lc0
    if ($LASTEXITCODE -ne 0) { throw 'Stockfish installation failed.' }
}
if (-not (Test-Path 'runtime\lc0.exe') -or -not (Test-Path 'runtime\dnnl.dll')) {
    $Lc0Url = 'https://github.com/LeelaChessZero/lc0/releases/download/v0.32.1/lc0-v0.32.1-windows-cpu-dnnl.zip'
    $Lc0Sha256 = 'B9CFCFBD3DABFFBFD452F6E8E087C22273721BEF48EBA19640B6D92006C142F5'
    $TempRoot = Join-Path ([IO.Path]::GetTempPath()) 'move-coach-lc0-v13'
    New-Item -ItemType Directory -Force $TempRoot | Out-Null
    $Archive = Join-Path $TempRoot 'lc0.zip'
    Invoke-WebRequest -Uri $Lc0Url -OutFile $Archive
    if ((Get-FileHash $Archive -Algorithm SHA256).Hash -ne $Lc0Sha256) {
        throw 'Lc0 Windows archive checksum mismatch.'
    }
    $Extract = Join-Path $TempRoot 'extract'
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $Extract
    Expand-Archive -Path $Archive -DestinationPath $Extract
    foreach ($Name in @('lc0.exe', 'dnnl.dll', 'mimalloc-override.dll', 'mimalloc-redirect.dll')) {
        $Source = Join-Path $Extract $Name
        if (-not (Test-Path $Source)) { throw "Lc0 archive is missing $Name." }
        Copy-Item $Source (Join-Path 'runtime' $Name) -Force
    }
}
if (-not (Test-Path 'runtime\lc0-gpu.exe') -or -not (Test-Path 'runtime\onnxruntime.dll')) {
    # Optional DirectML build. It uses the Windows graphics runtime and does
    # not require cudart64_12.dll or a separately installed CUDA toolkit.
    $GpuUrl = 'https://github.com/LeelaChessZero/lc0/releases/download/v0.32.1/lc0-v0.32.1-windows-onnx-dml.zip'
    $GpuSha256 = '86AAC242B3A1C6986D02ACC33B8CC64175B11A21B6941C62443C07FA18AC7539'
    $GpuTemp = Join-Path ([IO.Path]::GetTempPath()) 'move-coach-lc0-gpu-v13'
    New-Item -ItemType Directory -Force $GpuTemp | Out-Null
    $GpuArchive = Join-Path $GpuTemp 'lc0-gpu.zip'
    Invoke-WebRequest -Uri $GpuUrl -OutFile $GpuArchive
    if ((Get-FileHash $GpuArchive -Algorithm SHA256).Hash -ne $GpuSha256) {
        throw 'Lc0 GPU archive checksum mismatch.'
    }
    $GpuExtract = Join-Path $GpuTemp 'extract'
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $GpuExtract
    Expand-Archive -Path $GpuArchive -DestinationPath $GpuExtract
    $GpuSource = Join-Path $GpuExtract 'lc0.exe'
    if (-not (Test-Path $GpuSource)) { throw 'Lc0 GPU archive is missing lc0.exe.' }
    Copy-Item $GpuSource 'runtime\lc0-gpu.exe' -Force
    $OnnxSource = Join-Path $GpuExtract 'onnxruntime.dll'
    if (-not (Test-Path $OnnxSource)) { throw 'Lc0 GPU archive is missing onnxruntime.dll.' }
    Copy-Item $OnnxSource 'runtime\onnxruntime.dll' -Force
    Set-Content -Path 'runtime\lc0-gpu-backend.txt' -Value 'onnx-dml' -NoNewline
}
& $VenvPython setup_lc0.py --lc0 runtime\lc0.exe
if ($LASTEXITCODE -ne 0) { throw 'Lc0 and weight installation failed.' }
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
Write-Host "Created windows\Output\MoveCoach-Setup-v13.exe"
