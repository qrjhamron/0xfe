# PyInstaller spec for the PySide6 Move Coach app (Patricia-only).
from pathlib import Path

PROJECT = Path(SPECPATH).parent
RUNTIME = PROJECT / 'runtime'


def required(path):
    if not path.exists():
        raise SystemExit(f'Missing app build input: {path}')
    return path


required(RUNTIME / 'patricia.exe')

a = Analysis(
    [str(PROJECT / 'run_app.py')],
    pathex=[str(PROJECT)],
    binaries=[(str(RUNTIME / 'patricia.exe'), 'runtime')],
    datas=[],
    hiddenimports=['coach_app.windows', 'coach_app.overlay', 'coach_app.controller',
                   'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
                   'PySide6.QtWebChannel'],
    excludes=['playwright', 'tkinter', 'matplotlib'],
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
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='MoveCoachApp',
)
