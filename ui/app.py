import os
import shutil
import sys
from pathlib import Path

try:
    from PyQt6.QtCore import QLibraryInfo, Qt
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import QApplication
except ImportError:
    pass

from core.command_loader import CommandCatalog
from core.config import Config
from ui.main_window import MainWindow
from ui.single_instance import SingleInstanceManager


def configure_linux_ime() -> None:
    """Configure Linux IME compatibility for Vietnamese and international input methods."""
    if sys.platform != "linux":
        return

    # Check available Qt platforminputcontext plugins in active PyQt6 bundle
    try:
        from PyQt6.QtCore import QLibraryInfo
        plugins_path = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))
        im_dir = plugins_path / "platforminputcontexts"
        available_im_plugins = {f.name for f in im_dir.glob("*.so")} if im_dir.is_dir() else set()
    except Exception:
        available_im_plugins = set()

    current_im = os.environ.get("QT_IM_MODULE", "")

    # When QT_IM_MODULE=fcitx is requested but PyQt6 lacks libfcitx5platforminputcontextplugin.so,
    # fcitx5 provides full IBus DBus emulation (org.freedesktop.IBus). Fall back to ibus plugin
    # so typing in Vietnamese (fcitx5-bamboo / fcitx5-unikey) works seamlessly.
    if current_im == "fcitx" and "libfcitx5platforminputcontextplugin.so" not in available_im_plugins:
        if "libibusplatforminputcontextplugin.so" in available_im_plugins:
            os.environ["QT_IM_MODULE"] = "ibus"
            return

    if not current_im:
        # Auto-detect running IME daemon if not explicitly set
        desktop_im = os.getenv("XMODIFIERS", "") or os.getenv("GTK_IM_MODULE", "")
        has_fcitx = shutil.which("fcitx5") is not None or "fcitx" in desktop_im
        has_ibus = shutil.which("ibus") is not None or "ibus" in desktop_im

        if has_fcitx:
            if "libfcitx5platforminputcontextplugin.so" in available_im_plugins:
                os.environ["QT_IM_MODULE"] = "fcitx"
            elif "libibusplatforminputcontextplugin.so" in available_im_plugins:
                os.environ["QT_IM_MODULE"] = "ibus"
        elif has_ibus and "libibusplatforminputcontextplugin.so" in available_im_plugins:
            os.environ["QT_IM_MODULE"] = "ibus"


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
    configure_linux_ime()

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
