# PyInstaller spec for the Windows V16 installer (Patricia-only build).
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules


PROJECT = Path(SPECPATH).parent
RUNTIME = PROJECT / 'runtime'


def required(path):
    if not path.exists():
        raise SystemExit(f'Missing Windows build input: {path}')
    return path


required(RUNTIME / 'patricia.exe')

datas = [
    (str(PROJECT / 'panel.js'), '.'),
    (str(PROJECT / 'overlay.js'), '.'),
    (str(PROJECT / 'opening_book.py'), '.'),
]
binaries = [
    (str(RUNTIME / 'patricia.exe'), 'runtime'),
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
