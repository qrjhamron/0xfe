"""Headless checks for the PySide6 desktop app (no display needed).

Covers the pure geometry, FEN history tracking, side resolution, and the
controller's opening-book path with the real Patricia worker. Qt widgets
are packaging-checked statically; the GUI itself is smoke-built by the
windows-app workflow.
"""
import chess

from coach_app.controller import CoachController
from coach_app.geometry import arrow_points, arrow_styles, resolve_side, square_center
from coach_app.snapshot import FenTracker

# Geometry mirrors the proven 800x800 web overlay space.
assert square_center('e4', False) == (450, 450)
assert square_center('e4', True) == (350, 350)
x1, y1, x2, y2 = arrow_points('e2e4', False)
assert (x1, y1) == (450, 650) and (x2, y2) == (450, 468), 'tip stops 18px before e4 center'
assert arrow_styles(3, 14)[0][1] > arrow_styles(3, 14)[2][1]
assert len(arrow_styles(9, 14)) == 3
print('PASS: overlay geometry and weaker-alt arrow styling')

# Side resolution: page API wins, orientation is the fallback.
assert resolve_side(1, True, 'auto') == 'white'
assert resolve_side(2, False, 'auto') == 'black'
assert resolve_side(None, True, 'auto') == 'black'
assert resolve_side(None, False, 'auto') == 'white'
assert resolve_side(1, False, 'black') == 'black'
assert resolve_side(None, False, 'both') is None
print('PASS: side resolution from API, preference, or orientation')

# FEN diffing rebuilds SAN history for the opening book.
tracker = FenTracker()
assert tracker.update(chess.STARTING_FEN) == ()
board = chess.Board()
board.push_san('e4')
assert tracker.update(board.fen()) == ('e4',)
board.push_san('e5')
assert tracker.update(board.fen()) == ('e4', 'e5')
assert tracker.update(board.fen()) == ('e4', 'e5'), 'unchanged FEN must be a no-op'
print('PASS: FEN tracker rebuilds opening history')

# Controller delivers the persona book move without touching the engine.
delivered = []
controller = CoachController(on_recommendation=delivered.append)
try:
    controller.update({'fen': chess.STARTING_FEN, 'flipped': False,
                       'playing': 1, 'result': '*',
                       'rect': {'x': 0, 'y': 0, 'w': 800, 'h': 800}})
    assert delivered and delivered[-1]['source'] == 'opening-book', delivered
    assert chess.Move.from_uci(delivered[-1]['move']) in chess.Board().legal_moves
finally:
    controller.close()
print('PASS: controller serves the opening book and legal first move')

# Static packaging contract: native overlay, tray, streaming exclusion.
from pathlib import Path
root = Path(__file__).resolve().parent
windows = (root / 'coach_app/windows.py').read_text()
overlay = (root / 'coach_app/overlay.py').read_text()
streaming = (root / 'coach_app/streaming.py').read_text()
snapshot = (root / 'coach_app/snapshot.py').read_text()
assert 'QWebEngineView' in windows and 'QSystemTrayIcon' in windows
assert 'SetWindowDisplayAffinity' in streaming and 'WDA_EXCLUDEFROMCAPTURE' in streaming
assert 'Mode Streaming' in windows and 'set_exclude_from_capture' in windows
assert 'createElement' not in snapshot, 'snapshot must stay read-only'
assert 'WA_TransparentForMouseEvents' in overlay
main_py = (root / 'coach_app/main.py').read_text()
assert 'PySide6-Addons' in main_py and 'belum terpasang' in main_py and '_webengine_missing' in main_py
assert 'from .windows import' not in main_py.split('def main')[0], 'windows import must stay lazy'
spec = (root / 'windows/MoveCoachApp.spec').read_text()
assert 'PySide6.QtWebEngineCore' in spec and 'PySide6.QtWebEngineWidgets' in spec
assert 'QtWebEngineProcess.exe' in spec and 'QtWebEngine file missing' in spec, \
    'spec must fail the build when QtWebEngine is absent'
reqs_app = (root / 'requirements-app.txt').read_text()
assert 'PySide6-Addons==6.11.0' in reqs_app and 'PySide6-Essentials==6.11.0' in reqs_app, \
    'PySide6 must stay pinned to 6.11 (6.12 removed QtWebEngine)'
build_ps1 = (root / 'windows/build_app.ps1').read_text()
assert 'Start-Process' in build_ps1 and '-Wait' in build_ps1, \
    'smoke test must wait for the GUI exe exit code'
assert 'Bundled QtWebEngine file missing' in build_ps1, \
    'build must verify the bundled WebEngine files exist'
print('PASS: native overlay, tray controls, and streaming exclusion are wired')
print('PASS: missing QtWebEngine fails with install instructions, not a traceback')
print('ALL DESKTOP APP CHECKS PASSED')
