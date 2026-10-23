"""Move Coach desktop app entry point (PySide6, tray-resident)."""
import ctypes
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

INSTALL_HINT = (
    'Komponen Qt WebEngine (PySide6-Addons) belum terpasang.\n\n'
    'Kalau menjalankan dari sumber, pasang dulu di environment proyek:\n'
    '    .venv\\Scripts\\python -m pip install -r requirements-app.txt\n'
    '(harus PySide6 6.11 — versi 6.12 sudah tidak memuat QtWebEngine)\n\n'
    'Kalau menjalankan dari ZIP rilis, ekstrak seluruh isi ZIP dulu '
    'sebelum membuka MoveCoach.exe (jangan jalankan dari pratinjau ZIP).'
)


def _webengine_missing():
    try:
        import PySide6.QtWebEngineWidgets  # noqa: F401
    except ImportError:
        return True
    return False


def _fail_friendly():
    print(INSTALL_HINT, file=sys.stderr)
    try:
        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(None, 'Move Coach — dependensi kurang', INSTALL_HINT)
    except Exception:
        pass
    return 1


def main():
    if _webengine_missing():
        return _fail_friendly()
    from .windows import TrayApp, app_icon
    if '--smoke' in sys.argv:
        # Headless packaging smoke test: build every window, then quit.
        import os
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-gpu --no-sandbox')
        from PySide6.QtCore import QTimer
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        tray = TrayApp(app)
        QTimer.singleShot(1500, app.quit)
        code = app.exec()
        tray.controller.close()
        print('SMOKE_OK')
        return code
    if sys.platform == 'win32':
        try:  # Stable taskbar/tray identity on Windows.
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                'MoveCoach.Patricia')
        except (AttributeError, OSError):
            pass
    app = QApplication(sys.argv)
    app.setApplicationName('Move Coach')
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(False)
    TrayApp(app)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
