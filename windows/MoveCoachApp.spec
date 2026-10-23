# PyInstaller spec for the PySide6 Move Coach app (Patricia-only).
from pathlib import Path

PROJECT = Path(SPECPATH).parent
RUNTIME = PROJECT / 'runtime'


def required(path):
    if not path.exists():
        raise SystemExit(f'Missing app build input: {path}')
    return path


required(RUNTIME / 'patricia.exe')

# Fail the build loudly if QtWebEngine is absent from the environment.
# PySide6-Addons 6.12 removed it; PyInstaller only warns about the missing
# hidden imports and would silently ship an exe that cannot start.
import PySide6

_PYSIDE = Path(PySide6.__file__).resolve().parent
for _name in ('QtWebEngineCore.pyd', 'QtWebEngineWidgets.pyd',
              'QtWebEngineProcess.exe', 'Qt6WebEngineCore.dll'):
    if not (_PYSIDE / _name).exists():
        raise SystemExit(
            f'QtWebEngine file missing from PySide6 install: {_name} '
            '(pin PySide6-Addons==6.11.0; 6.12 has no QtWebEngine)')

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
