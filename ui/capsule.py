"""Self-contained CAsk capsule representing an independent assistant card."""

from __future__ import annotations

from typing import Dict, List, Optional

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


def is_worker_active(worker) -> bool:
    """Safely check if an APIWorker thread is active without raising on deleted C++ objects."""
    if worker is None:
        return False
    try:
        from PyQt6 import sip
        if sip.isdeleted(worker):
            return False
    except Exception:
        pass
    try:
        return worker.isRunning()
    except (RuntimeError, Exception):
        return False


class CAskCapsule(QWidget):
    """Independent CAsk interactive card holding input, loading, and result states."""

    STATE_INPUT = 0
    STATE_LOADING = 1
    STATE_RESULT = 2

    close_requested = pyqtSignal(object)  # Emits self
    size_changed = pyqtSignal(object)    # Emits self
    state_changed = pyqtSignal(object, int)  # Emits (self, state)
    reorder_requested = pyqtSignal(object, int)  # Emits (self, direction: -1 or +1)
    toggle_on_top_requested = pyqtSignal()
    drag_started = pyqtSignal(object, object)  # Emits (self, QPoint global pos)
    drag_moved = pyqtSignal(object, object)    # Emits (self, QPoint global pos)
    drag_ended = pyqtSignal(object, object)    # Emits (self, QPoint global pos)

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
        self._chat_history: List[Dict[str, str]] = []
        self._turn_count: int = 1
        self._current_system_prompt: str = ""
        self._current_badge: str = ""

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
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Container frame
        self.container = QFrame(self)
        self.container.setObjectName("CentralContainer")
        self.container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

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
        self.input_bar.reorder_requested.connect(lambda direction: self.reorder_requested.emit(self, direction))
        self.input_bar.toggle_on_top_requested.connect(self.toggle_on_top_requested)
        self.stack.addWidget(self.input_bar)

        # 1. Loading View
        self.loading_widget = LoadingIndicator(parent=self)
        self.stack.addWidget(self.loading_widget)

        # 2. Result View
        self.result_view = ResultView(catalog=self.catalog, parent=self)
        self.result_view.dismiss_requested.connect(lambda: self.close_requested.emit(self))
        self.result_view.return_to_input_requested.connect(self._handle_return_to_input)
        self.result_view.reorder_requested.connect(lambda direction: self.reorder_requested.emit(self, direction))
        self.result_view.toggle_on_top_requested.connect(self.toggle_on_top_requested)
        self.result_view.drag_started.connect(lambda pt: self.drag_started.emit(self, pt))
        self.result_view.drag_moved.connect(lambda pt: self.drag_moved.emit(self, pt))
        self.result_view.drag_ended.connect(lambda pt: self.drag_ended.emit(self, pt))
        self.result_view.followup_submitted.connect(self._handle_followup_submit)
        self.stack.addWidget(self.result_view)

        layout.addWidget(self.container)

    def stop_worker(self) -> None:
        """Safely detach, cancel, and terminate any background worker thread."""
        worker = self._worker
        self._worker = None
        if worker is None:
            return

        try:
            from PyQt6 import sip
            if sip.isdeleted(worker):
                return
        except Exception:
            pass

        try:
            worker.cancel()
        except (RuntimeError, Exception):
            pass

        try:
            worker.finished.disconnect()
        except (RuntimeError, Exception):
            pass

        try:
            worker.error.disconnect()
        except (RuntimeError, Exception):
            pass

        try:
            if worker.isRunning():
                worker.quit()
                worker.wait(400)
        except (RuntimeError, Exception):
            pass

    def closeEvent(self, event) -> None:
        """Reap active threads before widget destruction."""
        self.stop_worker()
        super().closeEvent(event)

    def _handle_return_to_input(self) -> None:
        """Switch from Result state back to Input state and focus input bar."""
        self.stop_worker()
        self._chat_history = []
        self._turn_count = 1
        self._current_system_prompt = ""
        self.switch_state(self.STATE_INPUT)
        self.input_bar.selectAll()
        self.input_bar.setFocus()

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

        # Stop any existing worker safely
        self.stop_worker()

        # Switch to Loading State
        self.loading_widget.set_loading_text(route.loading_label)
        self.switch_state(self.STATE_LOADING)

        # Reset conversation thread state
        self._chat_history = []
        self._turn_count = 1
        self._current_system_prompt = route.system_prompt
        self._current_badge = f"/{route.command}" if route.command else "Assistant"
        badge_name = self._current_badge

        # Launch background API request (parent=None prevents Qt deleteChildren race)
        worker = APIWorker(
            system_prompt=route.system_prompt,
            user_prompt_content=route.user_prompt_content,
            config=self.config,
            history=None,
            parent=None,
        )
        self._worker = worker

        def _on_initial_finish(res: str) -> None:
            self._worker = None
            self._chat_history.append({"role": "user", "content": route.user_prompt_content})
            self._chat_history.append({"role": "assistant", "content": res})
            self._show_result(badge_name, res, is_error=False)

        def _on_initial_error(err: str) -> None:
            self._worker = None
            self._show_result(f"Error [{badge_name}]", f"### Request Failed\n\n{err}", is_error=True)

        worker.finished.connect(_on_initial_finish)
        worker.error.connect(_on_initial_error)
        worker.start()

    def _handle_followup_submit(self, followup_text: str) -> None:
        """Submit a follow-up prompt within the current conversation thread, supporting slash commands."""
        if self._turn_count >= self.config.max_followup_turns:
            return
        if is_worker_active(self._worker):
            return

        self.stop_worker()

        # Parse follow-up query with command router
        route = route_input(followup_text, self.catalog, self.config)

        if route.route_type == RouteType.HELP:
            self.result_view.append_turn(
                user_query=followup_text,
                ai_response=route.display_text or "",
                current_turn=self._turn_count,
                max_turns=self.config.max_followup_turns,
            )
            self.size_changed.emit(self)
            return

        if route.route_type in (RouteType.MISSING_ARG, RouteType.UNKNOWN_COMMAND):
            self.result_view.append_turn(
                user_query=followup_text,
                ai_response=f"⚠️ {route.display_text}",
                current_turn=self._turn_count,
                max_turns=self.config.max_followup_turns,
            )
            self.size_changed.emit(self)
            return

        if not self.config.has_any_api_key:
            self.result_view.append_turn(
                user_query=followup_text,
                ai_response="⚠️ **Error:** No API key configured in `config.env`.",
                current_turn=self._turn_count,
                max_turns=self.config.max_followup_turns,
            )
            self.size_changed.emit(self)
            return

        # Adopt command system prompt if a slash command was used, otherwise retain active persona
        if route.route_type == RouteType.COMMAND:
            system_prompt = route.system_prompt
            prompt_content = route.user_prompt_content
            self._current_system_prompt = route.system_prompt
            self._current_badge = f"/{route.command}"
        else:
            system_prompt = self._current_system_prompt
            prompt_content = followup_text

        # Disable input while waiting for model response
        self.result_view.followup_input.setEnabled(False)
        loading_hint = f"Thinking [{route.loading_label}]..." if route.loading_label else "Thinking..."
        self.result_view.followup_input.setPlaceholderText(loading_hint)
        self.result_view.turn_badge.setText(f"{self._turn_count}/{self.config.max_followup_turns} (thinking)")

        worker = APIWorker(
            system_prompt=system_prompt,
            user_prompt_content=prompt_content,
            config=self.config,
            history=list(self._chat_history),
            parent=None,
        )
        self._worker = worker

        def _on_followup_finish(res: str) -> None:
            self._worker = None
            self._chat_history.append({"role": "user", "content": prompt_content})
            self._chat_history.append({"role": "assistant", "content": res})
            self._turn_count += 1
            self.result_view.append_turn(
                user_query=followup_text,
                ai_response=res,
                current_turn=self._turn_count,
                max_turns=self.config.max_followup_turns,
            )
            self.size_changed.emit(self)

        def _on_followup_error(err: str) -> None:
            self._worker = None
            error_msg = f"⚠️ **Request Failed:** {err}"
            self.result_view.append_turn(
                user_query=followup_text,
                ai_response=error_msg,
                current_turn=self._turn_count,
                max_turns=self.config.max_followup_turns,
            )
            self.size_changed.emit(self)

        worker.finished.connect(_on_followup_finish)
        worker.error.connect(_on_followup_error)
        worker.start()

    def _show_result(self, badge: str, content: str, is_error: bool = False) -> None:
        """Render response with elastic dynamic auto-expansion."""
        self.result_view.set_content(
            badge,
            content,
            is_error=is_error,
            current_turn=self._turn_count,
            max_turns=self.config.max_followup_turns,
        )
        self.switch_state(self.STATE_RESULT)

