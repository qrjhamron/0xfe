"""Qt windows: embedded Chess.com board, native overlay, tray controls."""
import json
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QIcon, QMouseEvent, QPainter, QPixmap
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QSystemTrayIcon

from app_paths import ROOT

from .controller import CoachController
from .geometry import square_center
from .overlay import ArrowOverlay
from .settings_store import (load_settings, save_settings, save_status,
                             settings_mtime)
from .snapshot import SNAPSHOT_JS
from .streaming import set_exclude_from_capture

START_URL = 'https://www.chess.com/play/computer'


def app_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor('#1b2420'))
    painter = QPainter(pixmap)
    painter.setPen(QColor('#8ce4bc'))
    font = painter.font()
    font.setPixelSize(36)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, 'M')
    painter.end()
    return QIcon(pixmap)


class BoardWindow(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setWindowTitle('Move Coach — Patricia')
        self.resize(1180, 860)
        profile = QWebEngineProfile('movecoach', self)
        profile.setPersistentStoragePath(str(ROOT / 'runtime' / 'web-profile'))
        self.view = QWebEngineView(self)
        self.view.setPage(QWebEnginePage(profile, self.view))
        self.view.setUrl(QUrl(START_URL))
        self.setCentralWidget(self.view)
        self.overlay = ArrowOverlay()
        self.last_rect = None
        self.last_flipped = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(250)
        controller.on_recommendation = self.show_recommendation
        controller.on_auto_move = self.execute_move

    def poll(self):
        self.view.page().runJavaScript(SNAPSHOT_JS, self._on_snapshot)

    def _on_snapshot(self, value):
        raw = None
        if isinstance(value, str) and value:
            try:
                raw = json.loads(value)
            except ValueError:
                raw = None
        if raw and raw.get('rect'):
            self.last_rect = raw['rect']
            self.last_flipped = bool(raw.get('flipped'))
            self._place_overlay()
        self.controller.update(raw)

    def _place_overlay(self):
        if not self.last_rect or not self.isVisible():
            self.overlay.hide()
            return
        rect = self.last_rect
        top_left = self.view.mapToGlobal(QPoint(int(rect['x']), int(rect['y'])))
        self.overlay.setGeometry(top_left.x(), top_left.y(),
                                 max(50, int(rect['w'])), max(50, int(rect['h'])))
        self.overlay.show()

    def show_recommendation(self, payload):
        if not payload:
            self.overlay.clear()
            return
        moves = [payload['move']] + [m for m in payload.get('candidates', [])
                                     if m != payload['move']]
        self.overlay.set_recommendation(
            moves, self.last_flipped,
            self.controller.settings['color'], self.controller.settings['width'])
        self._place_overlay()

    def execute_move(self, move_uci):
        if not self.last_rect:
            return
        rect = self.last_rect
        def point(square):
            cx, cy = square_center(square, self.last_flipped)
            return QPointF(rect['x'] + cx / 800 * rect['w'],
                           rect['y'] + cy / 800 * rect['h'])
        target = self.view.focusProxy() or self.view
        def click(pos):
            for kind in (QMouseEvent.Type.MouseButtonPress,
                         QMouseEvent.Type.MouseButtonRelease):
                QApplication.sendEvent(target, QMouseEvent(
                    kind, pos, Qt.MouseButton.LeftButton,
                    Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
        click(point(move_uci[0:2]))
        QTimer.singleShot(70, lambda: click(point(move_uci[2:4])))

    def moveEvent(self, event):
        super().moveEvent(event)
        self._place_overlay()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_overlay()

    def closeEvent(self, event):
        # Closing the board parks it in the tray instead of quitting.
        event.ignore()
        self.hide()
        self.overlay.hide()


def panel_command():
    """Command that launches the separate panel app."""
    if getattr(sys, 'frozen', False):
        sibling = Path(sys.executable).resolve().with_name('MoveCoachPanel.exe')
        if sibling.exists():
            return [str(sibling)]
        return [sys.executable, '--panel']
    return [sys.executable, str(ROOT / 'run_panel.py')]


class TrayApp:
    def __init__(self, app):
        self.app = app
        self.controller = CoachController()
        self.controller.settings.update(load_settings())
        self.controller.on_status = self._on_status
        self._last_status = None
        self._settings_stamp = settings_mtime()
        self.board = BoardWindow(self.controller)
        self.tray = QSystemTrayIcon(app_icon(), app)
        self.panel_proc = None
        menu = QMenu()
        menu.addAction('Papan', self._show_board)
        menu.addAction('Panel Pengaturan', self.launch_panel)
        menu.addSeparator()
        self.stream_action = QAction('Mode Streaming', menu, checkable=True)
        self.stream_action.toggled.connect(self._streaming_toggled)
        menu.addAction(self.stream_action)
        menu.addSeparator()
        menu.addAction('Keluar', self._quit)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip('Move Coach — Patricia')
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()
        panel_action = QAction('Panel Pengaturan', self.board)
        panel_action.triggered.connect(self.launch_panel)
        self.board.menuBar().addAction(panel_action)
        self.board_stream_action = QAction('Mode Streaming', self.board,
                                           checkable=True)
        self.board_stream_action.toggled.connect(self._streaming_toggled)
        self.board.menuBar().addAction(self.board_stream_action)
        self._sync_streaming(bool(self.controller.settings.get('streaming')))
        self.settings_timer = QTimer(self.board)
        self.settings_timer.timeout.connect(self._poll_settings)
        self.settings_timer.start(500)
        self.board.show()
        # The panel is its own app; open it right away next to the board.
        self.launch_panel()

    def launch_panel(self):
        if '--smoke' in sys.argv:
            return
        if self.panel_proc is not None and self.panel_proc.poll() is None:
            return
        try:
            self.panel_proc = subprocess.Popen(panel_command())
        except OSError:
            self.panel_proc = None

    def _poll_settings(self):
        stamp = settings_mtime()
        if stamp is None or stamp == self._settings_stamp:
            return
        self._settings_stamp = stamp
        loaded = load_settings()
        self.controller.settings.update(loaded)
        self._sync_streaming(bool(loaded.get('streaming')))

    def _sync_streaming(self, enabled):
        # Arrows vanish from capture; the board itself stays visible so
        # the stream still shows the game. The panel app excludes itself.
        set_exclude_from_capture(self.board.overlay, enabled)
        for action in (self.stream_action, self.board_stream_action):
            if action.isChecked() != enabled:
                action.blockSignals(True)
                action.setChecked(enabled)
                action.blockSignals(False)

    def _streaming_toggled(self, enabled):
        loaded = load_settings()
        loaded['streaming'] = enabled
        save_settings(loaded)
        self._settings_stamp = settings_mtime()
        self.controller.settings['streaming'] = enabled
        self._sync_streaming(enabled)

    def _on_status(self, text):
        if text != self._last_status:
            self._last_status = text
            save_status(text)

    def _show_board(self):
        self.board.show()
        self.board.raise_()
        self.board.activateWindow()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_board()

    def _quit(self):
        if self.panel_proc is not None and self.panel_proc.poll() is None:
            self.panel_proc.terminate()
        self.controller.close()
        self.tray.hide()
        self.app.quit()
