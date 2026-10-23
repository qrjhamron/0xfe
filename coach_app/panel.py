"""Move Coach panel: a separate app for Patricia settings.

Runs as its own process (MoveCoachPanel.exe) next to the main board app.
Every change is written to the shared settings file and the main app
applies it within a poll tick; the engine status line travels back the
same way. This module must never import the WebEngine window layer, so
the panel stays light and starts even without QtWebEngine.
"""
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QHBoxLayout,
                               QLabel, QVBoxLayout, QWidget)

from presets import PRESETS

from .settings_store import load_settings, load_status, save_settings
from .streaming import set_exclude_from_capture

STYLE_ITEMS = (
    ('Solid · selalu terbaik', 'solid'),
    ('Seimbang · manusiawi', 'balanced'),
    ('Agresif · menyerang', 'aggressive'),
    ('Liar · berani beda', 'wild'),
    ('Asli · tanpa tuning', 'original'),
)


def panel_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor('#1b2420'))
    painter = QPainter(pixmap)
    painter.setPen(QColor('#8ce4bc'))
    font = painter.font()
    font.setPixelSize(36)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, 'P')
    painter.end()
    return QIcon(pixmap)


class PanelWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Move Coach — Panel Pengaturan')
        self.resize(360, 560)
        self.settings = load_settings()
        layout = QVBoxLayout(self)
        self.skill_label = QLabel()
        layout.addWidget(self.skill_label)
        self.status = QLabel('Menyiapkan…')
        layout.addWidget(self.status)
        layout.addWidget(QLabel(
            'Panel ini aplikasi terpisah — perubahan langsung berlaku '
            'di papan aplikasi utama.'))

        self.level_buttons = {}
        grid = QVBoxLayout()
        row = None
        for index, elo in enumerate(PRESETS):
            if index % 3 == 0:
                row = QHBoxLayout()
                grid.addLayout(row)
            button = _level_button(elo, self.set_elo)
            row.addWidget(button)
            self.level_buttons[elo] = button
        layout.addLayout(grid)

        self.style = QComboBox()
        for label, value in STYLE_ITEMS:
            self.style.addItem(label, value)
        self.style.currentIndexChanged.connect(self._style_changed)
        layout.addWidget(QLabel('Gaya Patricia'))
        layout.addWidget(self.style)

        self.enabled = _toggle('Rekomendasi aktif', 'enabled', self)
        layout.addWidget(self.enabled)
        self.auto_move = _toggle('Auto move (klik di aplikasi utama)', 'autoMove', self)
        layout.addWidget(self.auto_move)
        self.book = _toggle('Buku persona', 'openingBook', self)
        layout.addWidget(self.book)
        self.streaming = QCheckBox(
            'Mode Streaming · sembunyikan panah & panel dari tangkapan layar')
        self.streaming.toggled.connect(self._streaming_changed)
        layout.addWidget(self.streaming)

        self._sync_from_settings()
        set_exclude_from_capture(self, bool(self.settings['streaming']))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll_status)
        self.timer.start(500)

    def _sync_from_settings(self):
        self.style.setCurrentIndex(
            max(0, self.style.findData(self.settings['style'])))
        self.enabled.setChecked(bool(self.settings['enabled']))
        self.auto_move.setChecked(bool(self.settings['autoMove']))
        self.book.setChecked(bool(self.settings['openingBook']))
        self.streaming.setChecked(bool(self.settings['streaming']))
        self._mark_elo()

    def _mark_elo(self):
        for value, button in self.level_buttons.items():
            button.setChecked(value == self.settings['elo'])
        from engine_runtime import patricia_skill_for_elo
        skill = patricia_skill_for_elo(self.settings['elo'])
        self.skill_label.setText(f'PATRICIA · Skill <b>{skill}</b>')

    def _save(self):
        save_settings(self.settings)

    def set_elo(self, elo):
        self.settings['elo'] = elo
        self._mark_elo()
        self._save()

    def _style_changed(self):
        self.settings['style'] = self.style.currentData()
        self._save()

    def set_flag(self, key, value):
        self.settings[key] = value
        self._save()

    def _streaming_changed(self, enabled):
        self.settings['streaming'] = enabled
        self._save()
        set_exclude_from_capture(self, enabled)
        self.status.setText('Mode Streaming aktif · panel tersembunyi dari siaran'
                            if enabled else 'Mode Streaming mati')

    def _poll_status(self):
        if not self.streaming.isChecked():
            self.status.setText(load_status())


def _level_button(elo, on_pick):
    from PySide6.QtWidgets import QPushButton
    button = QPushButton(str(elo))
    button.setCheckable(True)
    button.clicked.connect(lambda _=False, e=elo: on_pick(e))
    return button


def _toggle(label, key, panel):
    box = QCheckBox(label)
    box.toggled.connect(lambda v, k=key: panel.set_flag(k, v))
    return box


def main():
    if '--smoke' in sys.argv:
        import os
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        app = QApplication(sys.argv)
        window = PanelWindow()
        window.show()
        QTimer.singleShot(800, app.quit)
        code = app.exec()
        print('SMOKE_PANEL_OK')
        return code
    app = QApplication(sys.argv)
    app.setApplicationName('Move Coach Panel')
    app.setWindowIcon(panel_icon())
    window = PanelWindow()
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
