"""QApplication setup and lifecycle management."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import QApplication
except ImportError:
    pass

from core.command_loader import CommandCatalog
from core.config import Config
from ui.main_window import MainWindow


def load_stylesheet() -> str:
    """Load QSS stylesheet from package directory."""
    qss_path = Path(__file__).resolve().parent / "styles.qss"
    if qss_path.is_file():
        try:
            return qss_path.read_text(encoding="utf-8")
        except OSError:
            pass
    return ""


def run_gui(
    config: Config,
    catalog: CommandCatalog,
    initial_input: str = "",
) -> int:
    """Initialize and run the PyQt6 GUI event loop."""
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    app.setApplicationName("Ctrans")
    app.setApplicationDisplayName("Ctrans Quick AI Assistant")
    app.setApplicationVersion("2.0.0")

    # Set default typography: JetBrainsMono Nerd Font with fallbacks
    font = QFont("JetBrainsMono Nerd Font")
    if not font.exactMatch():
        font = QFont("JetBrains Mono")
    if not font.exactMatch():
        font = QFont("Inter")
    if not font.exactMatch():
        font = QFont("Sans Serif")
    font.setPointSize(11)
    app.setFont(font)

    # Load glassmorphic stylesheet
    stylesheet = load_stylesheet()
    if stylesheet:
        app.setStyleSheet(stylesheet)

    window = MainWindow(config=config, catalog=catalog, initial_input=initial_input)
    window.show()
    window.raise_()
    window.activateWindow()

    return app.exec()
