"""Interactive Settings HUD for managing, reordering, and testing AI response models."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Dict, List, Optional

try:
    from PyQt6.QtCore import Qt, pyqtSignal
    from PyQt6.QtGui import QCursor, QFont
    from PyQt6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    pass

from core.api_client import APIClient
from core.config import Config, load_config, save_config_file
from ui.icons import (
    get_arrow_down_icon,
    get_arrow_up_icon,
    get_exit_icon,
    get_eye_icon,
    get_gear_icon,
    get_test_icon,
)


class ModelCardWidget(QFrame):
    """Visual card for a single AI model provider with priority, credentials, and ping test."""

    reorder_requested = pyqtSignal(object, int)  # Emits (self, direction: -1 for up, +1 for down)
    status_changed = pyqtSignal()

    def __init__(
        self,
        provider_id: str,
        display_name: str,
        presets: List[str],
        default_model: str,
        default_base_url: str = "",
        is_custom: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.provider_id = provider_id
        self.display_name = display_name
        self.presets = presets
        self.default_model = default_model
        self.default_base_url = default_base_url
        self.is_custom = is_custom
        self._is_key_visible = False
        self._test_thread: Optional[threading.Thread] = None

        self.setObjectName("ModelCard")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)

        # Header bar: Checkbox, Name, Priority Badge, Up/Down buttons
        header = QHBoxLayout()
        header.setSpacing(8)

        self.checkbox = QCheckBox(self)
        self.checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.checkbox.toggled.connect(lambda _: self.status_changed.emit())
        header.addWidget(self.checkbox)

        self.title_label = QLabel(self.display_name, self)
        self.title_label.setObjectName("CardTitle")
        font = self.title_label.font()
        font.setBold(True)
        self.title_label.setFont(font)
        header.addWidget(self.title_label)

        self.badge = QLabel("[Primary]", self)
        self.badge.setObjectName("PriorityBadge")
        header.addWidget(self.badge)

        header.addStretch(1)

        # Up / Down arrow buttons
        self.up_btn = QToolButton(self)
        self.up_btn.setObjectName("CardArrowBtn")
        self.up_btn.setIcon(get_arrow_up_icon())
        self.up_btn.setToolTip("Move up in priority")
        self.up_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.up_btn.clicked.connect(lambda: self.reorder_requested.emit(self, -1))
        header.addWidget(self.up_btn)

        self.down_btn = QToolButton(self)
        self.down_btn.setObjectName("CardArrowBtn")
        self.down_btn.setIcon(get_arrow_down_icon())
        self.down_btn.setToolTip("Move down in priority")
        self.down_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.down_btn.clicked.connect(lambda: self.reorder_requested.emit(self, 1))
        header.addWidget(self.down_btn)

        layout.addLayout(header)

        # Form fields (Model, API Key, Base URL if custom)
        form = QGridLayout()
        form.setContentsMargins(0, 2, 0, 0)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)

        # Model Selector
        row = 0
        lbl_model = QLabel("Model:", self)
        lbl_model.setObjectName("CardFieldLabel")
        form.addWidget(lbl_model, row, 0)

        self.model_combo = QComboBox(self)
        self.model_combo.setObjectName("ModelComboBox")
        self.model_combo.setEditable(True)
        for p in self.presets:
            self.model_combo.addItem(p)
        self.model_combo.setCurrentText(self.default_model)
        form.addWidget(self.model_combo, row, 1, 1, 2)

        # Base URL field for Custom / 9Router
        if self.is_custom:
            row += 1
            lbl_url = QLabel("Base URL:", self)
            lbl_url.setObjectName("CardFieldLabel")
            form.addWidget(lbl_url, row, 0)

            self.base_url_input = QLineEdit(self)
            self.base_url_input.setObjectName("SettingsInput")
            self.base_url_input.setPlaceholderText("http://localhost:20128/v1")
            self.base_url_input.setText(self.default_base_url)
            form.addWidget(self.base_url_input, row, 1, 1, 2)
        else:
            self.base_url_input = None

        # API Key Field
        row += 1
        lbl_key = QLabel("API Key:", self)
        lbl_key.setObjectName("CardFieldLabel")
        form.addWidget(lbl_key, row, 0)

        key_box = QHBoxLayout()
        key_box.setSpacing(4)

        self.key_input = QLineEdit(self)
        self.key_input.setObjectName("SettingsInput")
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        hint = "Optional for local 9Router" if self.is_custom else f"Paste {self.display_name} Key"
        self.key_input.setPlaceholderText(hint)
        key_box.addWidget(self.key_input, 1)

        self.eye_btn = QToolButton(self)
        self.eye_btn.setObjectName("EyeToggleBtn")
        self.eye_btn.setIcon(get_eye_icon(visible=False))
        self.eye_btn.setToolTip("Show / Hide Key")
        self.eye_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.eye_btn.clicked.connect(self._toggle_key_visibility)
        key_box.addWidget(self.eye_btn)

        form.addLayout(key_box, row, 1, 1, 2)

        # Test Connection row
        row += 1
        test_box = QHBoxLayout()
        test_box.setSpacing(8)

        self.test_btn = QPushButton("Test", self)
        self.test_btn.setObjectName("TestPingBtn")
        self.test_btn.setIcon(get_test_icon())
        self.test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.test_btn.clicked.connect(self._run_connection_test)
        test_box.addWidget(self.test_btn)

        self.test_result = QLabel("", self)
        self.test_result.setObjectName("TestResultLabel")
        test_box.addWidget(self.test_result, 1)

        form.addLayout(test_box, row, 1, 1, 2)

        layout.addLayout(form)

    def _toggle_key_visibility(self) -> None:
        self._is_key_visible = not self._is_key_visible
        mode = QLineEdit.EchoMode.Normal if self._is_key_visible else QLineEdit.EchoMode.Password
        self.key_input.setEchoMode(mode)
        self.eye_btn.setIcon(get_eye_icon(visible=self._is_key_visible))

    def _run_connection_test(self) -> None:
        if self._test_thread and self._test_thread.is_alive():
            return

        self.test_btn.setEnabled(False)
        self.test_result.setText("Testing...")
        self.test_result.setStyleSheet("color: #f9e2af;")

        model = self.model_combo.currentText().strip()
        api_key = self.key_input.text().strip()
        base_url = self.base_url_input.text().strip() if self.base_url_input else ""

        def _worker():
            success, latency, msg = APIClient.test_provider_connection(
                provider_type=self.provider_id,
                model=model,
                api_key=api_key,
                base_url=base_url,
                timeout=8,
            )
            # Update UI on main thread safely
            def _apply():
                self.test_btn.setEnabled(True)
                if success:
                    self.test_result.setText(f"✓ {latency}s ({msg})")
                    self.test_result.setStyleSheet("color: #a6e3a1; font-weight: bold;")
                else:
                    snippet = msg[:40] + "..." if len(msg) > 40 else msg
                    self.test_result.setText(f"✗ {snippet}")
                    self.test_result.setStyleSheet("color: #f38ba8;")

            try:
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, _apply)
            except Exception:
                pass

        self._test_thread = threading.Thread(target=_worker, daemon=True)
        self._test_thread.start()

    def set_priority_badge(self, text: str, is_active: bool) -> None:
        self.badge.setText(text)
        if not is_active:
            self.badge.setStyleSheet("color: #6c7086; background: rgba(108, 112, 134, 0.15);")
        elif "Primary" in text:
            self.badge.setStyleSheet("color: #a6e3a1; background: rgba(166, 227, 161, 0.15);")
        else:
            self.badge.setStyleSheet("color: #89b4fa; background: rgba(137, 180, 250, 0.15);")


class SettingsView(QFrame):
    """Full-featured Settings HUD view embedded inside the CAsk capsule."""

    saved = pyqtSignal(object)  # Emits reloaded Config object
    closed = pyqtSignal()

    def __init__(self, config: Config, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.setObjectName("SettingsView")
        self.cards: List[ModelCardWidget] = []
        self._setup_ui()
        self.load_from_config(self.config)

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 14, 18, 14)
        main_layout.setSpacing(12)

        # Header Title & Close button
        header = QHBoxLayout()
        header.setSpacing(8)

        icon_label = QLabel(self)
        icon_label.setPixmap(get_gear_icon("#f9e2af", size=20).pixmap(20, 20))
        header.addWidget(icon_label)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title = QLabel("Response Model Pipeline", self)
        title.setObjectName("SettingsHeaderTitle")
        title_box.addWidget(title)

        subtitle = QLabel("Set provider priority, toggle fallbacks, or test connections.", self)
        subtitle.setObjectName("SettingsHeaderSubtitle")
        title_box.addWidget(subtitle)

        header.addLayout(title_box, 1)

        close_btn = QToolButton(self)
        close_btn.setObjectName("SettingsCloseBtn")
        close_btn.setIcon(get_exit_icon())
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.closed.emit)
        header.addWidget(close_btn)

        main_layout.addLayout(header)

        # Scrollable area for cards
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("SettingsScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(10)

        # Create Model Cards with presets
        self.card_groq = ModelCardWidget(
            provider_id="groq",
            display_name="Groq Cloud (LPU Instant)",
            presets=["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"],
            default_model="qwen/qwen3.8-27b",
            parent=self.cards_container,
        )

        self.card_gemini = ModelCardWidget(
            provider_id="gemini",
            display_name="Google Gemini",
            presets=["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash"],
            default_model="gemini-flash-lite-latest",
            parent=self.cards_container,
        )

        self.card_custom = ModelCardWidget(
            provider_id="custom_openai",
            display_name="9Router / Custom OpenAI",
            presets=["claude-3-5-sonnet", "gpt-4o", "deepseek-chat", "qwen2.5-coder:32b"],
            default_model="claude-3-5-sonnet",
            default_base_url="http://localhost:20128/v1",
            is_custom=True,
            parent=self.cards_container,
        )

        for card in [self.card_groq, self.card_gemini, self.card_custom]:
            card.reorder_requested.connect(self._handle_card_reorder)
            card.status_changed.connect(self._refresh_priority_badges)
            self.cards.append(card)
            self.cards_layout.addWidget(card)

        self.cards_layout.addStretch(1)
        self.scroll_area.setWidget(self.cards_container)
        main_layout.addWidget(self.scroll_area, 1)

        # Footer Actions
        footer = QHBoxLayout()
        footer.setSpacing(10)

        self.footer_status = QLabel("", self)
        self.footer_status.setObjectName("SettingsFooterStatus")
        footer.addWidget(self.footer_status, 1)

        self.cancel_btn = QPushButton("Cancel", self)
        self.cancel_btn.setObjectName("SettingsCancelBtn")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.closed.emit)
        footer.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save & Apply", self)
        self.save_btn.setObjectName("SettingsSaveBtn")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.clicked.connect(self._handle_save)
        footer.addWidget(self.save_btn)

        main_layout.addLayout(footer)

    def load_from_config(self, config: Config) -> None:
        """Populate inputs from runtime configuration."""
        self.config = config

        # Groq
        self.card_groq.model_combo.setCurrentText(config.groq_model or "qwen/qwen3.8-27b")
        self.card_groq.key_input.setText(config.groq_api_key or "")

        # Gemini
        self.card_gemini.model_combo.setCurrentText(config.gemini_model or "gemini-flash-lite-latest")
        self.card_gemini.key_input.setText(config.gemini_api_key or "")

        # Custom / 9Router
        self.card_custom.model_combo.setCurrentText(config.custom_openai_model or "claude-3-5-sonnet")
        self.card_custom.key_input.setText(config.custom_openai_api_key or "")
        if self.card_custom.base_url_input:
            self.card_custom.base_url_input.setText(config.custom_openai_base_url or "http://localhost:20128/v1")

        # Ordering & Checked status
        pipeline = list(config.provider_order) if config.provider_order else ["groq", "gemini"]

        # Sort self.cards according to pipeline order
        def _sort_key(c: ModelCardWidget) -> int:
            if c.provider_id in pipeline:
                return pipeline.index(c.provider_id)
            return len(pipeline) + 10

        self.cards.sort(key=_sort_key)

        # Update checked status
        for card in self.cards:
            is_enabled = card.provider_id in pipeline
            card.checkbox.setChecked(is_enabled)

        self._rebuild_cards_layout()
        self._refresh_priority_badges()
        self.footer_status.setText("")

    def _handle_card_reorder(self, card: ModelCardWidget, direction: int) -> None:
        idx = self.cards.index(card)
        new_idx = idx + direction
        if 0 <= new_idx < len(self.cards):
            self.cards[idx], self.cards[new_idx] = self.cards[new_idx], self.cards[idx]
            self._rebuild_cards_layout()
            self._refresh_priority_badges()

    def _rebuild_cards_layout(self) -> None:
        # Clear layout items without deleting widgets
        while self.cards_layout.count() > 0:
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

        for card in self.cards:
            self.cards_layout.addWidget(card)
        self.cards_layout.addStretch(1)

    def _refresh_priority_badges(self) -> None:
        active_rank = 1
        for card in self.cards:
            if card.checkbox.isChecked():
                if active_rank == 1:
                    card.set_priority_badge("[Primary]", True)
                else:
                    card.set_priority_badge(f"[Fallback {active_rank - 1}]", True)
                active_rank += 1
            else:
                card.set_priority_badge("[Inactive]", False)

    def _handle_save(self) -> None:
        """Persist settings to ~/.config/cask/config.env and hot-reload."""
        active_providers = [c.provider_id for c in self.cards if c.checkbox.isChecked()]
        provider_order_str = ",".join(active_providers)

        updates: Dict[str, str] = {
            "PROVIDER_ORDER": provider_order_str,
            "GROQ_MODEL": self.card_groq.model_combo.currentText().strip(),
            "GROQ_API_KEY": self.card_groq.key_input.text().strip(),
            "GEMINI_MODEL": self.card_gemini.model_combo.currentText().strip(),
            "GEMINI_API_KEY": self.card_gemini.key_input.text().strip(),
            "CUSTOM_OPENAI_MODEL": self.card_custom.model_combo.currentText().strip(),
            "CUSTOM_OPENAI_API_KEY": self.card_custom.key_input.text().strip(),
        }
        if self.card_custom.base_url_input:
            updates["CUSTOM_OPENAI_BASE_URL"] = self.card_custom.base_url_input.text().strip()

        try:
            target_file = save_config_file(updates)
            new_config = load_config(script_dir=self.config.script_dir)
            self.config = new_config
            self.footer_status.setText(f"✓ Saved to {target_file.name}")
            self.footer_status.setStyleSheet("color: #a6e3a1; font-weight: bold;")
            self.saved.emit(new_config)
        except Exception as e:
            self.footer_status.setText(f"Error saving: {e}")
            self.footer_status.setStyleSheet("color: #f38ba8;")
