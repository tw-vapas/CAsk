"""Self-contained CAsk capsule representing an independent assistant card."""

from __future__ import annotations

from typing import Optional

try:
    from PyQt6.QtCore import QRect, Qt, pyqtSignal
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import (
        QFrame,
        QGraphicsDropShadowEffect,
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


class CAskCapsule(QWidget):
    """Independent CAsk interactive card holding input, loading, and result states."""

    STATE_INPUT = 0
    STATE_LOADING = 1
    STATE_RESULT = 2

    close_requested = pyqtSignal(object)  # Emits self
    size_changed = pyqtSignal(object)    # Emits self
    state_changed = pyqtSignal(object, int)  # Emits (self, state)

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
        self._state: int = self.STATE_INPUT

        self._setup_ui()

        if self.initial_input:
            self.input_bar.setText(self.initial_input)
            self._handle_submit(self.initial_input)

    @property
    def state(self) -> int:
        return self._state

    @property
    def is_pinned(self) -> bool:
        if self._state == self.STATE_RESULT:
            return self.result_view.is_pinned
        return False

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Container frame
        self.container = QFrame(self)
        self.container.setObjectName("CentralContainer")

        try:
            shadow = QGraphicsDropShadowEffect(self.container)
            shadow.setBlurRadius(36)
            shadow.setOffset(0, 6)
            shadow.setColor(QColor(0, 0, 0, 160))
            self.container.setGraphicsEffect(shadow)
        except Exception:
            pass

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self.stack = QStackedLayout()
        container_layout.addLayout(self.stack)

        # 0. Input View
        self.input_bar = InputBar(catalog=self.catalog, parent=self)
        self.input_bar.submitted.connect(self._handle_submit)
        self.input_bar.cancelled.connect(lambda: self.close_requested.emit(self))
        self.input_bar.height_changed.connect(lambda _: self.size_changed.emit(self))
        self.stack.addWidget(self.input_bar)

        # 1. Loading View
        self.loading_widget = LoadingIndicator(parent=self)
        self.stack.addWidget(self.loading_widget)

        # 2. Result View
        self.result_view = ResultView(parent=self)
        self.result_view.dismiss_requested.connect(lambda: self.close_requested.emit(self))
        self.stack.addWidget(self.result_view)

        layout.addWidget(self.container)

    def switch_state(self, state: int) -> None:
        """Switch active state inside this capsule."""
        self._state = state
        self.stack.setCurrentIndex(state)

        if state == self.STATE_INPUT:
            self.input_bar.setFocus()
        elif state == self.STATE_LOADING:
            self.loading_widget.start()
        elif state == self.STATE_RESULT:
            self.loading_widget.stop()
            self.result_view.text_browser.setFocus()

        self.state_changed.emit(self, state)
        self.size_changed.emit(self)

    def calculate_ideal_height(self, available_width: int = 600, max_available_height: int = 840) -> int:
        """Calculate desired height based on current active state."""
        if self._state == self.STATE_INPUT:
            return self.input_bar.calculate_ideal_height(available_width)
        elif self._state == self.STATE_LOADING:
            return 54
        elif self._state == self.STATE_RESULT:
            ideal_h = int(self.result_view.calculate_ideal_height(available_width) * 1.35)
            min_h = 190
            max_h = min(840, max(300, max_available_height))
            return max(min_h, min(max_h, ideal_h))
        return 50

    def _handle_submit(self, text: str) -> None:
        """Process entered text via router and trigger API or immediate modal."""
        route = route_input(text, self.catalog, self.config)

        if route.route_type == RouteType.EMPTY:
            self.close_requested.emit(self)
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
        self.switch_state(self.STATE_LOADING)

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
        """Render response with elastic dynamic auto-expansion."""
        self.result_view.set_content(badge, content, is_error=is_error)
        self.switch_state(self.STATE_RESULT)
