"""Frameless Glassmorphic HUD Window with dynamic state machine."""

from __future__ import annotations

from typing import Optional

try:
    from PyQt6.QtCore import QEvent, QPoint, QRect, QSize, Qt
    from PyQt6.QtGui import QCursor, QGuiApplication
    from PyQt6.QtWidgets import (
        QFrame,
        QStackedLayout,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    pass

from core.api_client import APIWorker
from core.command_loader import CommandCatalog
from core.config import Config
from core.router import RouteType, route_input
from ui.input_bar import InputBar
from ui.loading_indicator import LoadingIndicator
from ui.result_view import ResultView


class MainWindow(QWidget):
    """Main Glassmorphism Raycast/Spotlight HUD."""

    STATE_INPUT = 0
    STATE_LOADING = 1
    STATE_RESULT = 2

    def __init__(
        self,
        config: Config,
        catalog: CommandCatalog,
        initial_input: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.catalog = catalog
        self.initial_input = initial_input
        self._worker: Optional[APIWorker] = None

        self._setup_window_properties()
        self._setup_ui()

        if self.initial_input:
            self.input_bar.setText(self.initial_input)
            self._handle_submit(self.initial_input)

    SHADOW_PAD_X = 24
    SHADOW_PAD_Y = 24

    def _setup_window_properties(self) -> None:
        """Configure frameless, translucent, always-on-top window flags."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setProperty("kwin_blur", True)

    def _setup_ui(self) -> None:
        """Build layout and state views."""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(
            self.SHADOW_PAD_X,
            self.SHADOW_PAD_Y,
            self.SHADOW_PAD_X,
            self.SHADOW_PAD_Y,
        )
        root_layout.setSpacing(0)

        # Central container frame with glassmorphism border and background
        self.container = QFrame(self)
        self.container.setObjectName("CentralContainer")

        # Deep floating drop-shadow effect (rgba(0, 0, 0, 0.40))
        try:
            from PyQt6.QtGui import QColor
            from PyQt6.QtWidgets import QGraphicsDropShadowEffect

            shadow = QGraphicsDropShadowEffect(self.container)
            shadow.setBlurRadius(32)
            shadow.setOffset(0, 4)
            shadow.setColor(QColor(0, 0, 0, 102))
            self.container.setGraphicsEffect(shadow)
        except Exception:
            pass

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Stacked layout for Input, Loading, and Result states
        self.stack = QStackedLayout()
        container_layout.addLayout(self.stack)

        # 0. Input View
        self.input_bar = InputBar(catalog=self.catalog, parent=self)
        self.input_bar.submitted.connect(self._handle_submit)
        self.input_bar.cancelled.connect(self.close)
        self.stack.addWidget(self.input_bar)

        # 1. Loading View
        self.loading_widget = LoadingIndicator(parent=self)
        self.stack.addWidget(self.loading_widget)

        # 2. Result View
        self.result_view = ResultView(parent=self)
        self.result_view.dismiss_requested.connect(self.close)
        self.stack.addWidget(self.result_view)

        root_layout.addWidget(self.container)

        self._switch_state(self.STATE_INPUT, target_width=600, target_height=50)

    def _get_target_screen(self):
        """Identify the screen under current mouse pointer."""
        cursor_pos = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor_pos)
        if not screen:
            screen = QGuiApplication.primaryScreen()
        return screen

    def _reposition(self, width: int, height: int) -> None:
        """Center the HUD horizontally and vertically on the target monitor."""
        screen = self._get_target_screen()
        if not screen:
            self.resize(width, height)
            return

        screen_geo = screen.availableGeometry()
        x = screen_geo.x() + (screen_geo.width() - width) // 2
        y = screen_geo.y() + (screen_geo.height() - height) // 2

        self.setGeometry(x, y, width, height)
        self.resize(width, height)
        self.move(x, y)

    def _switch_state(self, state: int, target_width: int, target_height: int) -> None:
        """Transition between UI states and adjust geometry."""
        self.stack.setCurrentIndex(state)
        self.container.setFixedSize(target_width, target_height)

        total_width = target_width + (self.SHADOW_PAD_X * 2)
        total_height = target_height + (self.SHADOW_PAD_Y * 2)
        self._reposition(total_width, total_height)

        if state == self.STATE_INPUT:
            self.input_bar.setFocus()
        elif state == self.STATE_LOADING:
            self.loading_widget.start()
        elif state == self.STATE_RESULT:
            self.loading_widget.stop()
            self.result_view.text_browser.setFocus()

    def _handle_submit(self, text: str) -> None:
        """Process entered text via router and trigger API or immediate modal."""
        route = route_input(text, self.catalog, self.config)

        if route.route_type == RouteType.EMPTY:
            self.close()
            return

        if route.route_type in (
            RouteType.HELP,
            RouteType.MISSING_ARG,
            RouteType.UNKNOWN_COMMAND,
        ):
            badge = "Help" if route.route_type == RouteType.HELP else "Usage"
            if route.route_type == RouteType.UNKNOWN_COMMAND:
                badge = "Unknown Command"
            self._show_result(badge, route.display_text or "", is_error=True)
            return

        # Check API key configuration before making network requests
        if not self.config.has_any_api_key:
            no_key_msg = (
                "### API Key not configured!\n\n"
                f"Please configure `GROQ_API_KEY` or `GEMINI_API_KEY` in:\n"
                f"`{self.config.config_dir / 'config.env'}`\n\n"
                "*(See `.env.example` in repo for instructions)*"
            )
            self._show_result("Config Error", no_key_msg, is_error=True)
            return

        # Switch to Loading State
        self.loading_widget.set_loading_text(route.loading_label)
        self._switch_state(self.STATE_LOADING, target_width=600, target_height=54)

        # Launch background API request
        badge_name = f"/{route.command}" if route.command else "Assistant"
        self._worker = APIWorker(
            system_prompt=route.system_prompt,
            user_prompt_content=route.user_prompt_content,
            config=self.config,
            parent=self,
        )
        self._worker.finished.connect(
            lambda res: self._show_result(badge_name, res, is_error=False)
        )
        self._worker.error.connect(
            lambda err: self._show_result(f"Error [{badge_name}]", f"### Request Failed\n\n{err}", is_error=True)
        )
        self._worker.start()

    def _show_result(self, badge: str, content: str, is_error: bool = False) -> None:
        """Render response in result state and auto-fit window height."""
        self.result_view.set_content(badge, content, is_error=is_error)

        screen = self._get_target_screen()
        max_h = 620
        if screen:
            max_h = min(620, screen.availableGeometry().height() - 100)

        # Estimate optimal height based on content line count
        line_count = max(4, len(content.splitlines()))
        calculated_h = min(max_h, max(180, line_count * 24 + 100))

        self._switch_state(self.STATE_RESULT, target_width=760, target_height=calculated_h)

    def changeEvent(self, event) -> None:
        """Detect window focus loss for Wayland click-outside-to-dismiss."""
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow():
                # Avoid closing if completer popup is active
                completer = self.input_bar.completer()
                if completer and completer.popup() and completer.popup().isVisible():
                    return
                self.close()

        super().changeEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            event.accept()
            return

        super().keyPressEvent(event)
