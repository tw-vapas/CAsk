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
        QSizePolicy,
        QTextEdit,
    )
except ImportError:
    pass

from core.command_loader import CommandCatalog


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

        self._max_length: int = 500
        self._completer: Optional[QCompleter] = None
        self._current_ideal_height: int = 50

        # Set placeholder text color to rgba(255, 255, 255, 0.55)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(255, 255, 255, 140))
        self.setPalette(palette)

        # Highlight only the leading command token
        self.highlighter = CommandHighlighter(self.document())

        if catalog:
            self._setup_completer(catalog)

        self.textChanged.connect(self._handle_text_changed)

    def calculate_ideal_height(self, available_width: Optional[int] = None) -> int:
        """Calculate dynamic height based on text content and line wrapping."""
        width = available_width if available_width is not None else self.width()
        if width <= 0:
            width = 600
        content_width = max(200, width - 36)
        raw_text = self.toPlainText()
        if not raw_text.strip():
            return 50

        doc = self.document().clone()
        doc.setTextWidth(content_width)
        doc_height = doc.size().height()
        if doc.lineCount() <= 1 and "\n" not in raw_text and doc_height <= 32:
            return 50

        computed = int(doc_height + 24)
        return max(50, min(220, computed))

    def sizeHint(self) -> QSize:
        return QSize(600, self.calculate_ideal_height())

    def minimumSizeHint(self) -> QSize:
        return QSize(200, 48)

    def text(self) -> str:
        return self.toPlainText()

    def setText(self, text: str) -> None:
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
        if new_height >= 220:
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

        # Window reorder shortcuts: Alt + Left / Right
        if (event.modifiers() & Qt.KeyboardModifier.AltModifier) and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            direction = -1 if event.key() == Qt.Key.Key_Left else 1
            self.reorder_requested.emit(direction)
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
            else:
                self.cancelled.emit()
            event.accept()
            return

        # Max length check for normal typing
        if self._max_length and len(self.text()) >= self._max_length and event.text():
            if event.key() not in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
                event.accept()
                return

        super().keyPressEvent(event)
