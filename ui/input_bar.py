"""Input bar widget with autocomplete for slash commands."""

from __future__ import annotations

from typing import Optional

try:
    from PyQt6.QtCore import Qt, pyqtSignal, QStringListModel
    from PyQt6.QtWidgets import QCompleter, QLineEdit, QListView
except ImportError:
    pass

from core.command_loader import CommandCatalog


class InputBar(QLineEdit):
    """Single-line input bar with autocomplete and keyboard navigation."""

    submitted = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(
        self,
        catalog: Optional[CommandCatalog] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("InputBar")
        self.setPlaceholderText("Ask anything, enter prompt, or /help for commands...")
        self.setMaxLength(500)
        self.setClearButtonEnabled(True)

        # Set placeholder text color to rgba(255, 255, 255, 0.4)
        palette = self.palette()
        from PyQt6.QtGui import QColor
        palette.setColor(palette.ColorRole.PlaceholderText, QColor(255, 255, 255, 102))
        self.setPalette(palette)

        if catalog:
            self._setup_completer(catalog)

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
            popup.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.setCompleter(completer)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            event.accept()
            return
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            text = self.text().strip()
            if text:
                self.submitted.emit(text)
            event.accept()
            return

        super().keyPressEvent(event)
