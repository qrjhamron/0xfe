"""Runtime paths shared by source and frozen Windows builds."""
import os
from pathlib import Path
import sys


def app_root() -> Path:
    override = os.environ.get('MOVE_COACH_ROOT')
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, 'frozen', False):
        folder = Path(sys.executable).resolve().parent
        # PyInstaller 6 may place collected files under ``_internal``.
        if not (folder / 'runtime').exists() and (folder / '_internal' / 'runtime').exists():
            folder = folder / '_internal'
        return folder
    return Path(__file__).resolve().parent


ROOT = app_root()
