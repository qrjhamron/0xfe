# PyInstaller spec for the Windows V15 installer, including the Maia sidecar.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules


PROJECT = Path(SPECPATH).parent
RUNTIME = PROJECT / 'runtime'


def required(path):
    if not path.exists():
        raise SystemExit(f'Missing Windows build input: {path}')
    return path


required(RUNTIME / 'stockfish.exe')
required(RUNTIME / 'lc0.exe')
required(RUNTIME / 'lc0-gpu.exe')
required(RUNTIME / 'onnxruntime.dll')
required(RUNTIME / 'lc0-gpu-backend.txt')
required(RUNTIME / 'dnnl.dll')
required(RUNTIME / 'mimalloc-override.dll')
required(RUNTIME / 'mimalloc-redirect.dll')
required(RUNTIME / 'lc0-install.json')
required(RUNTIME / 'patricia.exe')
required(RUNTIME / 'maia3-install.json')
for weight in ('meangirl-7.pb.gz', 'evilgyal-6.pb.gz', 'goodgyal-5.pb.gz', 'badgyal-8.pb.gz'):
    required(RUNTIME / 'lc0-weights' / weight)

datas = [
    (str(PROJECT / 'panel.js'), '.'),
    (str(PROJECT / 'overlay.js'), '.'),
    (str(PROJECT / 'calibration-profiles.json'), '.'),
    (str(PROJECT / 'opening_book.py'), '.'),
    (str(RUNTIME / 'lc0-install.json'), 'runtime'),
    (str(RUNTIME / 'lc0-gpu-backend.txt'), 'runtime'),
    (str(RUNTIME / 'maia3-install.json'), 'runtime'),
]
datas += [(str(RUNTIME / 'lc0-weights' / name), 'runtime/lc0-weights')
          for name in ('meangirl-7.pb.gz', 'evilgyal-6.pb.gz',
                       'goodgyal-5.pb.gz', 'badgyal-8.pb.gz')]
# Keep the Hugging Face cache offline and inside the installer.  The cache is
# intentionally enumerated instead of using a wildcard so PyInstaller keeps
# its original nested blob names.
MAIA_CACHE = RUNTIME / 'maia3-cache'
for cache_file in MAIA_CACHE.rglob('*'):
    if cache_file.is_file():
        datas.append((str(cache_file), str(Path('runtime/maia3-cache') / cache_file.relative_to(MAIA_CACHE).parent)))
binaries = [
    (str(RUNTIME / 'stockfish.exe'), 'runtime'),
    (str(RUNTIME / 'patricia.exe'), 'runtime'),
    (str(RUNTIME / 'lc0.exe'), 'runtime'),
    (str(RUNTIME / 'lc0-gpu.exe'), 'runtime'),
    (str(RUNTIME / 'onnxruntime.dll'), 'runtime'),
    (str(RUNTIME / 'dnnl.dll'), 'runtime'),
    (str(RUNTIME / 'mimalloc-override.dll'), 'runtime'),
    (str(RUNTIME / 'mimalloc-redirect.dll'), 'runtime'),
]

a = Analysis(
    [str(PROJECT / 'run.py')],
    pathex=[str(PROJECT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=['playwright.sync_api', 'chess.engine'] + collect_submodules('playwright'),
    excludes=['torch', 'tensorflow', 'numpy', 'matplotlib'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MoveCoach',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

# Maia and PyTorch stay in a separate process. This avoids loading a 700 MB
# CPU torch runtime into the main launcher while still shipping a zero-setup
# local engine in the Windows installer.
maia_analysis = Analysis(
    [str(PROJECT / 'maia_worker.py')],
    pathex=[str(PROJECT)],
    binaries=[],
    datas=collect_data_files('maia3'),
    hiddenimports=collect_submodules('maia3'),
    noarchive=False,
)
maia_pyz = PYZ(maia_analysis.pure)
maia_exe = EXE(
    maia_pyz,
    maia_analysis.scripts,
    [],
    exclude_binaries=True,
    name='maia-worker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    maia_exe,
    maia_analysis.binaries,
    maia_analysis.datas,
    strip=False,
    upx=False,
    name='MoveCoach',
)
