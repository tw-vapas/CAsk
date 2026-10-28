"""Markdown result viewer widget with header bar and copy button."""

from __future__ import annotations

try:
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QPushButton,
        QTextBrowser,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    pass


class ResultView(QWidget):
    """Rich text / Markdown viewer with 1-click clipboard copy."""

    dismiss_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ResultViewWidget")

        self._raw_content = ""

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 14, 18, 14)
        main_layout.setSpacing(10)

        # Header bar
        header_widget = QWidget(self)
        header_widget.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)

        self.badge_label = QLabel("Result", header_widget)
        self.badge_label.setObjectName("BadgeLabel")
        header_layout.addWidget(self.badge_label)

        header_layout.addStretch()

        self.copy_button = QPushButton("Copy", header_widget)
        self.copy_button.setObjectName("CopyButton")
        self.copy_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_button.clicked.connect(self._copy_to_clipboard)
        header_layout.addWidget(self.copy_button)

        main_layout.addWidget(header_widget)

        # Text browser
        self.text_browser = QTextBrowser(self)
        self.text_browser.setObjectName("ResultText")
        self.text_browser.setOpenExternalLinks(True)
        self.text_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        main_layout.addWidget(self.text_browser)

    def set_content(self, badge: str, content: str, is_error: bool = False) -> None:
        """Render markdown content and set badge indicator."""
        self._raw_content = content
        self.badge_label.setText(badge)
        if is_error:
            self.badge_label.setStyleSheet("color: #f87171; background-color: rgba(248, 113, 113, 0.15);")
        else:
            self.badge_label.setStyleSheet("")

        self.text_browser.setMarkdown(content)
        self.copy_button.setText("Copy")

    def get_document_ideal_height(self) -> int:
        """Calculate desired document height for dynamic window expansion."""
        doc = self.text_browser.document()
        if doc:
            return int(doc.size().height()) + 80
        return 200

    def _copy_to_clipboard(self) -> None:
        """Copy active response text to the system clipboard."""
        if not self._raw_content:
            return

        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(self._raw_content)

        self.copy_button.setText("✓ Copied!")
        QTimer.singleShot(1500, lambda: self.copy_button.setText("Copy"))

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.dismiss_requested.emit()
            event.accept()
            return

        super().keyPressEvent(event)
