"""Loading indicator widget for API request state."""

from __future__ import annotations

try:
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget
except ImportError:
    pass


class LoadingIndicator(QWidget):
    """Subtle animated loading state indicator."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("LoadingWidget")

        self._base_text = "Analyzing..."
        self._dot_count = 0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.label = QLabel(self._base_text, self)
        self.label.setObjectName("LoadingLabel")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

        self.timer = QTimer(self)
        self.timer.setInterval(350)
        self.timer.timeout.connect(self._animate_step)

    def set_loading_text(self, text: str) -> None:
        """Update loading status label."""
        self._base_text = text.rstrip(".")
        self._dot_count = 0
        self.label.setText(f"{self._base_text}...")

    def start(self) -> None:
        """Start animation loop."""
        self._dot_count = 0
        self.timer.start()

    def stop(self) -> None:
        """Stop animation loop."""
        self.timer.stop()

    def _animate_step(self) -> None:
        self._dot_count = (self._dot_count + 1) % 4
        dots = "." * self._dot_count
        self.label.setText(f"{self._base_text}{dots}")
