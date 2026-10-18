# PyInstaller spec for the Windows V13 installer.
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules


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
for weight in ('meangirl-7.pb.gz', 'evilgyal-6.pb.gz', 'goodgyal-5.pb.gz', 'badgyal-8.pb.gz'):
    required(RUNTIME / 'lc0-weights' / weight)

datas = [
    (str(PROJECT / 'panel.js'), '.'),
    (str(PROJECT / 'overlay.js'), '.'),
    (str(PROJECT / 'calibration-profiles.json'), '.'),
    (str(PROJECT / 'opening_book.py'), '.'),
    (str(RUNTIME / 'lc0-install.json'), 'runtime'),
    (str(RUNTIME / 'lc0-gpu-backend.txt'), 'runtime'),
]
datas += [(str(RUNTIME / 'lc0-weights' / name), 'runtime/lc0-weights')
          for name in ('meangirl-7.pb.gz', 'evilgyal-6.pb.gz',
                       'goodgyal-5.pb.gz', 'badgyal-8.pb.gz')]
binaries = [
    (str(RUNTIME / 'stockfish.exe'), 'runtime'),
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
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='MoveCoach',
)
