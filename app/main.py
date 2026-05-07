"""LeanPDF entry point."""
from __future__ import annotations

import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow

_ICON_PATH = os.path.join(os.path.dirname(__file__), "assets", "leadpdf_icon.svg")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("LeanPDF")
    app.setStyle("Fusion")
    if os.path.exists(_ICON_PATH):
        app.setWindowIcon(QIcon(_ICON_PATH))
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
