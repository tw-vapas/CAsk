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

from core.markdown_renderer import render_markdown_to_html
from ui.icons import get_copy_icon, get_exit_icon, get_grip_icon, get_pin_icon, get_search_icon


class ResultView(QFrame):
    """Rich text / Markdown viewer with 1-click actions and keyboard shortcuts."""

    dismiss_requested = pyqtSignal()
    pin_toggled = pyqtSignal(bool)
    return_to_input_requested = pyqtSignal()
    reorder_requested = pyqtSignal(int)  # -1 for left, +1 for right
    drag_started = pyqtSignal(object)  # Emits QPoint global position
    drag_moved = pyqtSignal(object)    # Emits QPoint global position
    drag_ended = pyqtSignal(object)    # Emits QPoint global position

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ResultViewWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._raw_content = ""
        self.is_pinned: bool = False
        self._drag_active: bool = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 14, 18, 14)
        main_layout.setSpacing(10)

        # Header bar
        header_widget = QWidget(self)
        header_widget.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        # Drag grip handle
        self.drag_handle = QPushButton(header_widget)
        self.drag_handle.setObjectName("DragHandle")
        self.drag_handle.setIcon(get_grip_icon())
        self.drag_handle.setToolTip("Drag to reorder window")
        self.drag_handle.setCursor(Qt.CursorShape.SizeAllCursor)
        self.drag_handle.setFixedWidth(24)
        self.drag_handle.installEventFilter(self)
        header_layout.addWidget(self.drag_handle)

        self.badge_label = QLabel("Result", header_widget)
        self.badge_label.setObjectName("BadgeLabel")
        header_layout.addWidget(self.badge_label)

        header_layout.addStretch()

        # 1. Ask button (icon kính lúp) - shortcut [Shift + A]
        self.ask_button = QPushButton("Ask", header_widget)
        self.ask_button.setObjectName("AskButton")
        self.ask_button.setIcon(get_search_icon())
        self.ask_button.setToolTip("Return to input bar / Ask [Shift + A]")
        self.ask_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ask_button.clicked.connect(self.return_to_input_requested.emit)
        header_layout.addWidget(self.ask_button)
        self.search_button = self.ask_button  # Backward-compatible alias

        # 2. Copy button (icon copy) - shortcut [Shift + C]
        self.copy_button = QPushButton("Copy", header_widget)
        self.copy_button.setObjectName("CopyButton")
        self.copy_button.setIcon(get_copy_icon())
        self.copy_button.setToolTip("Copy response [Shift + C]")
        self.copy_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_button.clicked.connect(self._copy_to_clipboard)
        header_layout.addWidget(self.copy_button)

        # 3. Pin button (icon pin) - shortcut [Shift + P]
        self.pin_button = QPushButton("Pin", header_widget)
        self.pin_button.setObjectName("PinButton")
        self.pin_button.setIcon(get_pin_icon(pinned=False))
        self.pin_button.setToolTip("Pin window [Shift + P]")
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

        # Render rich HTML with full GFM tables, lists, and LaTeX math formulas
        rendered_html = render_markdown_to_html(content)
        self.text_browser.setHtml(rendered_html)
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
        self.pin_button.setToolTip("Unpin window [Shift + P]" if self.is_pinned else "Pin window [Shift + P]")

        style = self.pin_button.style()
        if style:
            style.unpolish(self.pin_button)
            style.polish(self.pin_button)
        self.pin_toggled.emit(self.is_pinned)

    def _handle_key_event(self, event: QKeyEvent) -> bool:
        """Process keyboard shortcuts (A, P, C, Esc, Enter)."""
        key = event.key()
        modifiers = event.modifiers()

        # Shortcut Shift + A: Return to input bar
        if key == Qt.Key.Key_A and (modifiers & Qt.KeyboardModifier.ShiftModifier):
            self.return_to_input_requested.emit()
            event.accept()
            return True

        # Shortcut Shift + Left / Right: Reorder window
        if (modifiers & Qt.KeyboardModifier.ShiftModifier) and key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            direction = -1 if key == Qt.Key.Key_Left else 1
            self.reorder_requested.emit(direction)
            event.accept()
            return True

        # Shortcut Shift + P: Toggle pin
        if key == Qt.Key.Key_P and (modifiers & Qt.KeyboardModifier.ShiftModifier):
            self._toggle_pin()
            event.accept()
            return True

        # Shortcut Shift + C / Ctrl + C: Copy
        if key == Qt.Key.Key_C:
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self._copy_to_clipboard()
                event.accept()
                return True
            elif modifiers & Qt.KeyboardModifier.ControlModifier:
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
        """Intercept key events from text browser and mouse drag events on drag_handle."""
        if obj == self.text_browser and event.type() == QEvent.Type.KeyPress:
            if self._handle_key_event(event):
                return True

        if obj == self.drag_handle:
            event_type = event.type()
            if event_type == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._drag_active = True
                    self.drag_started.emit(event.globalPosition().toPoint())
                    return True
            elif event_type == QEvent.Type.MouseMove:
                if self._drag_active:
                    self.drag_moved.emit(event.globalPosition().toPoint())
                    return True
            elif event_type == QEvent.Type.MouseButtonRelease:
                if self._drag_active and event.button() == Qt.MouseButton.LeftButton:
                    self._drag_active = False
                    self.drag_ended.emit(event.globalPosition().toPoint())
                    return True

        return super().eventFilter(obj, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._handle_key_event(event):
            return
        super().keyPressEvent(event)
