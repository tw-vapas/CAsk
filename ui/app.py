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
from ui.single_instance import SingleInstanceManager


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

    app.setApplicationName("cask")
    app.setApplicationDisplayName("CAsk Quick AI Assistant")
    app.setDesktopFileName("cask")
    app.setApplicationVersion("2.0.0")

    # Enforce single instance: if another instance is already running, activate it and exit
    manager = SingleInstanceManager(app_name="cask")
    if not manager.try_acquire(initial_input=initial_input):
        return 0

    # Set default typography: JetBrainsMono Nerd Font with monospace fallback
    font = QFont("JetBrainsMono Nerd Font")
    if not font.exactMatch():
        font = QFont("JetBrains Mono")
    if not font.exactMatch():
        font = QFont("monospace")
    font.setPointSize(12)
    app.setFont(font)

    # Load glassmorphic stylesheet
    stylesheet = load_stylesheet()
    if stylesheet:
        app.setStyleSheet(stylesheet)

    window = MainWindow(config=config, catalog=catalog, initial_input=initial_input)
    manager.register_window(window)
    app.aboutToQuit.connect(manager.cleanup)

    window.show()
    window.raise_()
    window.activateWindow()

    try:
        return app.exec()
    finally:
        manager.cleanup()
