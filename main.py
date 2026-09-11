from __future__ import annotations

import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(HERE, "src")
sys.path.insert(0, SRC_DIR)


def _asset_path(*parts: str) -> str:
    candidates = [
        os.path.join(SRC_DIR, "assets", *parts),
        os.path.join(HERE, "assets", *parts),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]

os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-logging --log-level=3")
os.environ.setdefault("QT_LOGGING_RULES", "qt.webenginecontext.debug=false")


def main() -> int:
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("beamplots.app")

    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QIcon
    from PyQt5.QtWidgets import QApplication
    from qfluentwidgets import setTheme
    
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)

    ico_path = _asset_path("icons", "IES.ico")
    if os.path.exists(ico_path):
        app.setWindowIcon(QIcon(ico_path))

    from models.theme_manager import ThemeManager
    setTheme(ThemeManager.saved_theme())

    from beamplot.gui.main_window import MainWindow

    window = MainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
