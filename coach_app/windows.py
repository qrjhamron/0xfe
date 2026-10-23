"""Qt windows: embedded Chess.com board, native overlay, tray controls."""
import json
import time

from PySide6.QtCore import QPoint, QPointF, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QIcon, QMouseEvent, QPainter, QPixmap
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QHBoxLayout,
                               QLabel, QMainWindow, QMenu, QPushButton,
                               QSystemTrayIcon, QVBoxLayout, QWidget)

from app_paths import ROOT
from presets import PRESETS

from .controller import CoachController
from .geometry import square_center
from .overlay import ArrowOverlay
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


class ControlWindow(QWidget):
    def __init__(self, controller, board_window, tray):
        super().__init__()
        self.controller = controller
        self.board_window = board_window
        self.tray = tray
        self.setWindowTitle('Move Coach — Kontrol')
        self.resize(360, 560)
        layout = QVBoxLayout(self)
        title = QLabel('PATRICIA · Skill <b>—</b>')
        title.setObjectName('skillLabel')
        self.skill_label = title
        layout.addWidget(title)
        self.status = QLabel('Menyiapkan…')
        layout.addWidget(self.status)
        controller.on_status = self.status.setText

        self.level_buttons = {}
        grid = QWidget()
        grid_layout = QVBoxLayout(grid)
        row = None
        for index, elo in enumerate(PRESETS):
            if index % 3 == 0:
                row = QHBoxLayout()
                grid_layout.addLayout(row)
            button = QPushButton(str(elo))
            button.setCheckable(True)
            button.clicked.connect(lambda _=False, e=elo: self.set_elo(e))
            row.addWidget(button)
            self.level_buttons[elo] = button
        layout.addWidget(grid)

        self.style = QComboBox()
        self.style.addItem('Solid · selalu terbaik', 'solid')
        self.style.addItem('Seimbang · manusiawi', 'balanced')
        self.style.addItem('Agresif · menyerang', 'aggressive')
        self.style.addItem('Liar · berani beda', 'wild')
        self.style.addItem('Asli · tanpa tuning', 'original')
        self.style.currentIndexChanged.connect(self._style_changed)
        layout.addWidget(QLabel('Gaya Patricia'))
        layout.addWidget(self.style)

        self.enabled = QCheckBox('Rekomendasi aktif')
        self.enabled.setChecked(True)
        self.enabled.toggled.connect(
            lambda v: self.controller.settings.__setitem__('enabled', v))
        layout.addWidget(self.enabled)
        self.auto_move = QCheckBox('Auto move (klik di dalam aplikasi)')
        self.auto_move.toggled.connect(
            lambda v: self.controller.settings.__setitem__('autoMove', v))
        layout.addWidget(self.auto_move)
        self.book = QCheckBox('Buku persona')
        self.book.setChecked(True)
        self.book.toggled.connect(
            lambda v: self.controller.settings.__setitem__('openingBook', v))
        layout.addWidget(self.book)
        self.streaming = QCheckBox('Mode Streaming · sembunyikan panah & panel dari tangkapan layar')
        self.streaming.toggled.connect(self._streaming_changed)
        layout.addWidget(self.streaming)
        show_board = QPushButton('Tampilkan Papan')
        show_board.clicked.connect(self._show_board)
        layout.addWidget(show_board)
        self.set_elo(self.controller.settings['elo'])

    def set_elo(self, elo):
        self.controller.settings['elo'] = elo
        for value, button in self.level_buttons.items():
            button.setChecked(value == elo)
        from engine_runtime import patricia_skill_for_elo
        skill = patricia_skill_for_elo(elo)
        self.skill_label.setText(f'PATRICIA · Skill <b>{skill}</b>')

    def _style_changed(self):
        self.controller.settings['style'] = self.style.currentData()

    def _show_board(self):
        self.board_window.show()
        self.board_window.raise_()
        self.board_window.activateWindow()

    def _streaming_changed(self, enabled):
        # Arrows and this control window vanish from capture; the board
        # itself stays visible so the stream still shows the game.
        set_exclude_from_capture(self.board_window.overlay, enabled)
        set_exclude_from_capture(self, enabled)
        self.status.setText('Mode Streaming aktif · panah tersembunyi dari siaran'
                            if enabled else 'Mode Streaming mati')


class TrayApp:
    def __init__(self, app):
        self.app = app
        self.controller = CoachController()
        self.board = BoardWindow(self.controller)
        self.tray = QSystemTrayIcon(app_icon(), app)
        self.control = ControlWindow(self.controller, self.board, self.tray)
        menu = QMenu()
        menu.addAction('Papan', self._show_board)
        menu.addAction('Kontrol', self.control.show)
        menu.addSeparator()
        self.stream_action = QAction('Mode Streaming', menu, checkable=True)
        self.stream_action.toggled.connect(self.control.streaming.setChecked)
        menu.addAction(self.stream_action)
        menu.addSeparator()
        menu.addAction('Keluar', self._quit)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip('Move Coach — Patricia')
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()
        self.board.show()

    def _show_board(self):
        self.board.show()
        self.board.raise_()
        self.board.activateWindow()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.control.show() if not self.control.isVisible() else self.control.hide()

    def _quit(self):
        self.controller.close()
        self.tray.hide()
        self.app.quit()
