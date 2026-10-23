"""Settings/status bridge between the main app and the separate panel app.

The panel runs as its own process, so the two apps talk through small JSON
files under ``runtime/``: the panel writes settings and the main app polls
and applies them; the main app writes its status line and the panel shows
it. Writes are atomic (tmp file + replace) so a poll never reads a torn
file.
"""
import json
import os
import time

from app_paths import ROOT

from .controller import DEFAULT_SETTINGS

RUNTIME_DIR = ROOT / 'runtime'
SETTINGS_PATH = RUNTIME_DIR / 'settings.json'
STATUS_PATH = RUNTIME_DIR / 'status.json'
DEFAULTS = {**DEFAULT_SETTINGS, 'streaming': False}


def _read(path):
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(payload), encoding='utf-8')
    os.replace(tmp, path)


def load_settings():
    merged = dict(DEFAULTS)
    merged.update(_read(SETTINGS_PATH))
    return merged


def save_settings(settings):
    _write(SETTINGS_PATH,
           {key: settings.get(key, DEFAULTS[key]) for key in DEFAULTS})


def settings_mtime():
    try:
        return SETTINGS_PATH.stat().st_mtime_ns
    except OSError:
        return None


def load_status():
    return _read(STATUS_PATH).get('text') or 'Menyiapkan…'


def save_status(text):
    _write(STATUS_PATH, {'text': text, 'ts': time.time()})
