"""Move Coach desktop app entry point (PySide6, tray-resident)."""
import ctypes
import sys

from PySide6.QtWidgets import QApplication

from .windows import TrayApp, app_icon


def main():
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
