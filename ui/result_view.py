"""Markdown result viewer widget with header bar, action buttons, and keyboard shortcuts."""

from __future__ import annotations

try:
    from PyQt6.QtCore import QEvent, Qt, QTimer, pyqtSignal
    from PyQt6.QtGui import QGuiApplication, QKeyEvent
    from PyQt6.QtWidgets import (
        QFrame,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QTextBrowser,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    pass

from core.math_formatter import format_math_in_markdown
from ui.icons import get_copy_icon, get_exit_icon, get_pin_icon, get_search_icon


class ResultView(QFrame):
    """Rich text / Markdown viewer with 1-click actions and keyboard shortcuts."""

    dismiss_requested = pyqtSignal()
    pin_toggled = pyqtSignal(bool)
    return_to_input_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ResultViewWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._raw_content = ""
        self.is_pinned: bool = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 14, 18, 14)
        main_layout.setSpacing(10)

        # Header bar
        header_widget = QWidget(self)
        header_widget.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self.badge_label = QLabel("Result", header_widget)
        self.badge_label.setObjectName("BadgeLabel")
        header_layout.addWidget(self.badge_label)

        header_layout.addStretch()

        # 1. Search button (icon kính lúp) - shortcut [A]
        self.search_button = QPushButton("Search", header_widget)
        self.search_button.setObjectName("SearchButton")
        self.search_button.setIcon(get_search_icon())
        self.search_button.setToolTip("Return to input bar [A]")
        self.search_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_button.clicked.connect(self.return_to_input_requested.emit)
        header_layout.addWidget(self.search_button)

        # 2. Copy button (icon copy) - shortcut [C]
        self.copy_button = QPushButton("Copy", header_widget)
        self.copy_button.setObjectName("CopyButton")
        self.copy_button.setIcon(get_copy_icon())
        self.copy_button.setToolTip("Copy response [C]")
        self.copy_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_button.clicked.connect(self._copy_to_clipboard)
        header_layout.addWidget(self.copy_button)

        # 3. Pin button (icon pin) - shortcut [P]
        self.pin_button = QPushButton("Pin", header_widget)
        self.pin_button.setObjectName("PinButton")
        self.pin_button.setIcon(get_pin_icon(pinned=False))
        self.pin_button.setToolTip("Pin window [P]")
        self.pin_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pin_button.setProperty("pinned", False)
        self.pin_button.clicked.connect(self._toggle_pin)
        header_layout.addWidget(self.pin_button)

        # 4. Exit button (icon X) - shortcut [Esc]
        self.close_button = QPushButton("Exit", header_widget)
        self.close_button.setObjectName("ExitButton")
        self.close_button.setIcon(get_exit_icon())
        self.close_button.setToolTip("Close card [Esc]")
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.clicked.connect(self.dismiss_requested.emit)
        header_layout.addWidget(self.close_button)

        main_layout.addWidget(header_widget)

        # Text browser
        self.text_browser = QTextBrowser(self)
        self.text_browser.setObjectName("ResultText")
        self.text_browser.setOpenExternalLinks(True)
        self.text_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.text_browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.text_browser.installEventFilter(self)
        main_layout.addWidget(self.text_browser)

    def set_content(self, badge: str, content: str, is_error: bool = False) -> None:
        """Render markdown content with math formula parsing and set badge indicator."""
        self._raw_content = content
        self.badge_label.setText(badge)
        if is_error:
            self.badge_label.setStyleSheet("color: #f87171; background-color: rgba(248, 113, 113, 0.15); border: 1px solid rgba(248, 113, 113, 0.35); border-radius: 6px; padding: 3px 8px; font-weight: bold;")
        elif badge.startswith("/"):
            # Command mode: bold yellow badge styling
            self.badge_label.setStyleSheet("color: #f9e2af; background-color: rgba(249, 226, 175, 0.15); border: 1px solid rgba(249, 226, 175, 0.35); border-radius: 6px; padding: 3px 8px; font-weight: bold;")
        else:
            self.badge_label.setStyleSheet("")

        # Parse AI math formulas into clean Unicode notation
        formatted_content = format_math_in_markdown(content)
        self.text_browser.setMarkdown(formatted_content)
        self.copy_button.setText("Copy")
        self.copy_button.setIcon(get_copy_icon())

    def calculate_ideal_height(self, available_width: int = 760) -> int:
        """Calculate desired container height based on natural markdown document dimensions."""
        content_width = max(300, available_width - 44)
        doc = self.text_browser.document().clone()
        doc.setTextWidth(content_width)
        doc_height = int(doc.size().height())
        overhead = 85
        return doc_height + overhead

    def get_document_ideal_height(self) -> int:
        """Backward-compatible alias for calculate_ideal_height."""
        return self.calculate_ideal_height()

    def _copy_to_clipboard(self) -> None:
        """Copy active response text to the system clipboard."""
        if not self._raw_content:
            return

        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(self._raw_content)

        self.copy_button.setText("✓ Copied!")
        QTimer.singleShot(1500, lambda: self.copy_button.setText("Copy"))

    def _toggle_pin(self) -> None:
        """Toggle pinned status of the response box."""
        self.is_pinned = not self.is_pinned
        self.pin_button.setProperty("pinned", self.is_pinned)
        self.pin_button.setText("Pinned" if self.is_pinned else "Pin")
        self.pin_button.setIcon(get_pin_icon(pinned=self.is_pinned))
        self.pin_button.setToolTip("Unpin window [P]" if self.is_pinned else "Pin window [P]")

        style = self.pin_button.style()
        if style:
            style.unpolish(self.pin_button)
            style.polish(self.pin_button)
        self.pin_toggled.emit(self.is_pinned)

    def _handle_key_event(self, event: QKeyEvent) -> bool:
        """Process keyboard shortcuts (A, P, C, Esc, Enter)."""
        key = event.key()
        modifiers = event.modifiers()

        # Shortcut A: Return to input bar
        if key == Qt.Key.Key_A and modifiers == Qt.KeyboardModifier.NoModifier:
            self.return_to_input_requested.emit()
            event.accept()
            return True

        # Shortcut P: Toggle pin
        if key == Qt.Key.Key_P and modifiers == Qt.KeyboardModifier.NoModifier:
            self._toggle_pin()
            event.accept()
            return True

        # Shortcut C: Copy
        if key == Qt.Key.Key_C:
            if modifiers == Qt.KeyboardModifier.NoModifier:
                self._copy_to_clipboard()
                event.accept()
                return True
            elif modifiers == Qt.KeyboardModifier.ControlModifier:
                if self.text_browser.textCursor().hasSelection():
                    self.text_browser.copy()
                else:
                    self._copy_to_clipboard()
                event.accept()
                return True

        # Shortcut Esc / Enter: Dismiss
        if key in (Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.is_pinned:
                event.accept()
                return True
            self.dismiss_requested.emit()
            event.accept()
            return True

        return False

    def eventFilter(self, obj, event) -> bool:
        """Intercept key events from text browser to support shortcuts."""
        if obj == self.text_browser and event.type() == QEvent.Type.KeyPress:
            if self._handle_key_event(event):
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._handle_key_event(event):
            return
        super().keyPressEvent(event)
