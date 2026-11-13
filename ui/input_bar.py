"""Input bar widget with autocomplete for slash commands and syntax highlighting."""

from __future__ import annotations

from typing import Optional

try:
    from PyQt6.QtCore import QEvent, QRegularExpression, QSize, QStringListModel, Qt, pyqtSignal
    from PyQt6.QtGui import (
        QColor,
        QFont,
        QKeyEvent,
        QPalette,
        QSyntaxHighlighter,
        QTextCharFormat,
        QTextCursor,
    )
    from PyQt6.QtWidgets import (
        QApplication,
        QCompleter,
        QMenu,
        QSizePolicy,
        QTextEdit,
        QToolButton,
    )
except ImportError:
    pass

from core.command_loader import CommandCatalog
from ui.icons import get_gear_icon


class CommandHighlighter(QSyntaxHighlighter):
    """Formats only the leading command token (e.g. '/ask') in bold yellow."""

    def __init__(self, document) -> None:
        super().__init__(document)
        self.cmd_fmt = QTextCharFormat()
        self.cmd_fmt.setForeground(QColor("#f9e2af"))
        self.cmd_fmt.setFontWeight(QFont.Weight.Bold)
        self.regex = QRegularExpression(r"^/[a-zA-Z0-9_-]*")

    def highlightBlock(self, text: str) -> None:
        match = self.regex.match(text)
        if match.hasMatch() and match.capturedLength() > 0:
            self.setFormat(match.capturedStart(), match.capturedLength(), self.cmd_fmt)


class InputBar(QTextEdit):
    """Single-line HUD input bar supporting token syntax highlighting and autocomplete."""

    submitted = pyqtSignal(str)
    cancelled = pyqtSignal()
    height_changed = pyqtSignal(int)
    reorder_requested = pyqtSignal(int)  # -1 for left, +1 for right
    toggle_on_top_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    selection_requested = pyqtSignal(str, str)

    def __init__(
        self,
        catalog: Optional[CommandCatalog] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("InputBar")
        self.setPlaceholderText("Type what's on your mind...")
        self.setAcceptRichText(False)
        self.setTabChangesFocus(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.document().setDocumentMargin(2)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        self.setInputMethodHints(Qt.InputMethodHint.ImhNone)

        self._max_length: int = 500
        self._completer: Optional[QCompleter] = None
        self._current_ideal_height: int = 50
        self._preedit_text: str = ""
        self._provider_config = None
        self._provider_controls = False

        # Set placeholder text color to rgba(255, 255, 255, 0.55)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(255, 255, 255, 140))
        self.setPalette(palette)

        # Settings gear button on top right
        self.settings_btn = QToolButton(self)
        self.settings_btn.setObjectName("SettingsButton")
        self.settings_btn.setIcon(get_gear_icon())
        self.settings_btn.setToolTip("Response Model Settings [Ctrl+,]")
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        self.provider_btn = QToolButton(self)
        self.provider_btn.setObjectName("QuickChoice")
        self.provider_btn.setToolTip("Choose provider")
        self.provider_btn.setAccessibleName("Provider")
        self.provider_btn.clicked.connect(self._open_provider_menu)
        self.model_btn = QToolButton(self)
        self.model_btn.setObjectName("QuickChoice")
        self.model_btn.setToolTip("Choose saved model configuration")
        self.model_btn.setAccessibleName("Model")
        self.model_btn.clicked.connect(self._open_model_menu)
        self.provider_btn.hide()
        self.model_btn.hide()

        # Highlight only the leading command token
        self.highlighter = CommandHighlighter(self.document())

        if catalog:
            self._setup_completer(catalog)

        self.textChanged.connect(self._handle_text_changed)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_controls()

    def _position_controls(self):
        if not hasattr(self, "settings_btn"):
            return
        if self._provider_controls:
            y = self.height() - 46
            self.settings_btn.setGeometry(self.width() - 44, y + 4, 28, 28)
            available = max(110, self.width() - 74)
            provider_width = min(self.provider_btn.sizeHint().width(), available // 2)
            model_width = min(self.model_btn.sizeHint().width(), available // 2)
            self.provider_btn.setGeometry(14, y, provider_width, 36)
            self.model_btn.setGeometry(self.width() - 54 - model_width, y, model_width, 36)
            return
        btn_size = 24
        margin_right = 10
        margin_top = 13
        self.settings_btn.setGeometry(
            self.width() - btn_size - margin_right,
            margin_top,
            btn_size,
            btn_size,
        )

    def set_provider_config(self, config):
        from core.provider_config import migrate_models
        self._provider_config = config
        self._providers = list(config.providers) if config.providers is not None else migrate_models(list(config.models))
        self._provider_controls = True
        self.provider_btn.show()
        self.model_btn.show()
        self.setViewportMargins(0, 0, 0, 48)
        candidates = [p for p in self._providers if p.enabled and p.active_model]
        self._selected_provider = next((p for p in candidates if p.id == config.selected_provider_id), candidates[0] if candidates else None)
        provider = self._selected_provider
        self.provider_btn.setText((provider.name if provider else "Add Provider") + "  ⌄")
        self.model_btn.setText((provider.active_model.name if provider else "Select Model") + "  ⌄")
        self.provider_btn.setToolTip(provider.name if provider else "Open Settings to connect a provider")
        self.model_btn.setToolTip(provider.active_model.name if provider else "Open Settings to add a model")
        self._position_controls()
        self.height_changed.emit(self.calculate_ideal_height())

    def _selection_menu(self, button):
        menu = QMenu(self)
        menu.setObjectName("QuickSelectionMenu")
        menu.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        button.setProperty("expanded", True)
        button.style().unpolish(button)
        button.style().polish(button)
        menu.aboutToHide.connect(lambda: self._close_selection_menu(button))
        self._quick_menu = menu
        return menu

    def _close_selection_menu(self, button):
        button.setProperty("expanded", False)
        button.style().unpolish(button)
        button.style().polish(button)
        self.setFocus()

    def _open_provider_menu(self):
        candidates = [p for p in self._providers if p.enabled and p.active_model]
        if not candidates:
            self.settings_requested.emit()
            return
        menu = self._selection_menu(self.provider_btn)
        for provider in candidates:
            item = menu.addAction(provider.name)
            item.setCheckable(True)
            item.setChecked(provider is self._selected_provider)
            item.triggered.connect(lambda checked=False, p=provider: self.selection_requested.emit(p.id, p.active_model_id))
        menu.popup(self.provider_btn.mapToGlobal(self.provider_btn.rect().bottomLeft()))

    def _open_model_menu(self):
        provider = self._selected_provider
        if not provider:
            self.settings_requested.emit()
            return
        menu = self._selection_menu(self.model_btn)
        for model in provider.models:
            item = menu.addAction(f"{model.name}  ·  {model.reasoning or 'Provider defaults'}")
            item.setCheckable(True)
            item.setChecked(model.id == provider.active_model_id)
            item.triggered.connect(lambda checked=False, m=model: self.selection_requested.emit(provider.id, m.id))
        menu.popup(self.model_btn.mapToGlobal(self.model_btn.rect().bottomLeft()))

    def calculate_ideal_height(self, available_width: Optional[int] = None) -> int:
        """Calculate dynamic height based on committed text, IME preedit text, and line wrapping."""
        width = available_width if available_width is not None else self.width()
        if width <= 0:
            width = 600
        content_width = max(200, width - 36)
        raw_text = self.toPlainText()
        preedit = getattr(self, "_preedit_text", "")
        if not raw_text.strip() and not preedit.strip():
            return 96 if self._provider_controls else 50

        doc = self.document().clone()
        doc.setTextWidth(content_width)
        if preedit:
            cursor = QTextCursor(doc)
            pos = min(self.textCursor().position(), max(0, doc.characterCount() - 1))
            cursor.setPosition(pos)
            cursor.insertText(preedit)

        doc_height = doc.size().height()
        if doc.lineCount() <= 1 and "\n" not in raw_text and "\n" not in preedit and doc_height <= 32:
            return 96 if self._provider_controls else 50

        computed = int(doc_height + 24)
        return max(96, min(264, computed + 44)) if self._provider_controls else max(50, min(220, computed))

    def sizeHint(self) -> QSize:
        return QSize(600, self.calculate_ideal_height())

    def minimumSizeHint(self) -> QSize:
        return QSize(200, 48)

    def text(self) -> str:
        return self.toPlainText()

    def setText(self, text: str) -> None:
        self._preedit_text = ""
        self.setPlainText(text)
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)

    def setMaxLength(self, length: int) -> None:
        self._max_length = length

    def maxLength(self) -> int:
        return self._max_length

    def setClearButtonEnabled(self, enabled: bool) -> None:
        """Compatibility stub for QLineEdit interface."""
        pass

    def completer(self) -> Optional[QCompleter]:
        return self._completer

    def setCompleter(self, completer: Optional[QCompleter]) -> None:
        if self._completer:
            try:
                self._completer.activated.disconnect(self._insert_completion)
            except Exception:
                pass
        self._completer = completer
        if not self._completer:
            return
        self._completer.setWidget(self)
        self._completer.activated.connect(self._insert_completion)

    def _setup_completer(self, catalog: CommandCatalog) -> None:
        """Setup command autocomplete dropdown popup."""
        completions = ["/help"] + [f"/{name}" for name in catalog.list_names()]
        model = QStringListModel(completions, self)

        completer = QCompleter(model, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setFilterMode(Qt.MatchFlag.MatchStartsWith)

        popup = completer.popup()
        if popup:
            popup.setObjectName("CompleterPopup")
            popup.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
            popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            if popup.viewport():
                popup.viewport().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            popup.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.setCompleter(completer)

    def _insert_completion(self, completion: str) -> None:
        """Replace leading command token with selected completion."""
        current = self.text()
        parts = current.split(" ", 1)
        if len(parts) > 1:
            new_text = f"{completion} {parts[1]}"
        else:
            new_text = f"{completion} "
        self.setText(new_text)

    def _handle_text_changed(self) -> None:
        """Update property and trigger autocomplete when typing slash commands."""
        raw_text = self.text()
        stripped = raw_text.strip()
        is_cmd = bool(stripped.startswith("/"))
        if self.property("is_command") != is_cmd:
            self.setProperty("is_command", is_cmd)

        # Dynamic height check
        new_height = self.calculate_ideal_height()
        if new_height >= (264 if self._provider_controls else 220):
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        else:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        if new_height != self._current_ideal_height:
            self._current_ideal_height = new_height
            self.height_changed.emit(new_height)

        if not self._completer:
            return

        # Show autocomplete only while typing the command itself (no trailing space)
        if stripped.startswith("/") and " " not in raw_text:
            self._completer.setCompletionPrefix(stripped)
            popup = self._completer.popup()
            if popup:
                self._completer.complete(self.rect())
        else:
            popup = self._completer.popup()
            if popup and popup.isVisible():
                popup.hide()

    def insertFromMimeData(self, source) -> None:
        """Normalize line breaks and enforce max length."""
        text = source.text().replace("\r\n", "\n").replace("\r", "\n")
        if self._max_length and len(self.text()) + len(text) > self._max_length:
            allowed = max(0, self._max_length - len(self.text()))
            text = text[:allowed]
        self.insertPlainText(text)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # Completer popup navigation
        if self._completer and self._completer.popup() and self._completer.popup().isVisible():
            if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Tab):
                index = self._completer.popup().currentIndex()
                if not index.isValid():
                    index = self._completer.popup().model().index(0, 0)
                if index.isValid():
                    self._completer.activated.emit(index.data())
                    self._completer.popup().hide()
                    event.accept()
                    return
            elif event.key() == Qt.Key.Key_Escape:
                self._completer.popup().hide()
                event.accept()
                return

        # Settings shortcut: Ctrl + Comma
        if (event.modifiers() & Qt.KeyboardModifier.ControlModifier) and event.key() == Qt.Key.Key_Comma:
            self.settings_requested.emit()
            event.accept()
            return

        # Window reorder shortcuts: Alt + Left / Right
        if (event.modifiers() & Qt.KeyboardModifier.AltModifier) and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            direction = -1 if event.key() == Qt.Key.Key_Left else 1
            self.reorder_requested.emit(direction)
            event.accept()
            return

        # Toggle always-on-top shortcut: Alt + H
        if (event.modifiers() & Qt.KeyboardModifier.AltModifier) and event.key() == Qt.Key.Key_H:
            self.toggle_on_top_requested.emit()
            event.accept()
            return

        # Prevent Up/Down arrow from scrolling single line when completer is not open
        if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            event.accept()
            return

        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            event.accept()
            return
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.insertPlainText("\n")
                event.accept()
                return

            app = QApplication.instance()
            im = app.inputMethod() if app else None
            if im and im.isVisible():
                event.ignore()
                return

            text = self.text().strip()
            if text:
                self.submitted.emit(text)
            event.accept()
            return

        # Max length check for normal typing
        if self._max_length and len(self.text()) >= self._max_length and event.text():
            if event.key() not in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
                event.accept()
                return

        super().keyPressEvent(event)

    def focusOutEvent(self, event) -> None:
        self._preedit_text = ""
        super().focusOutEvent(event)

    def inputMethodEvent(self, event) -> None:
        """Handle IME composition and commit events for Vietnamese and CJK input methods."""
        self._preedit_text = event.preeditString() if hasattr(event, "preeditString") else ""
        super().inputMethodEvent(event)
        self._handle_text_changed()

    def inputMethodQuery(self, query) -> object:
        """Provide accurate geometry and surrounding context queries to IME engine."""
        return super().inputMethodQuery(query)
