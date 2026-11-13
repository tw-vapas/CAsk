"""Interactive Settings HUD for managing, reordering, adding, and testing AI response models."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Dict, List, Optional

try:
    from PyQt6.QtCore import QCoreApplication, QEvent, QTimer, Qt, pyqtSignal
    from PyQt6.QtGui import QCursor, QFont, QWheelEvent
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
from core.model_config import (
    PRESETS,
    ModelEntry,
    create_entry_from_preset,
    load_models_config,
    save_models_config,
)
from ui.icons import (
    get_arrow_down_icon,
    get_arrow_up_icon,
    get_exit_icon,
    get_eye_icon,
    get_gear_icon,
    get_plus_icon,
    get_test_icon,
    get_trash_icon,
)


class WheelSafeComboBox(QComboBox):
    """Let the containing panel scroll without changing a closed dropdown."""

    def setEditable(self, editable: bool) -> None:
        super().setEditable(editable)
        if editable:
            self.lineEdit().installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if watched is self.lineEdit() and event.type() == QEvent.Type.Wheel:
            self.wheelEvent(event)
            return True
        return super().eventFilter(watched, event)

    def wheelEvent(self, event) -> None:
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, QScrollArea):
                viewport = parent.viewport()
                forwarded = QWheelEvent(
                    viewport.mapFromGlobal(event.globalPosition()),
                    event.globalPosition(), event.pixelDelta(), event.angleDelta(),
                    event.buttons(), event.modifiers(), event.phase(), event.inverted(),
                )
                QCoreApplication.sendEvent(viewport, forwarded)
                event.setAccepted(forwarded.isAccepted())
                return
            parent = parent.parentWidget()
        event.ignore()


class ModelCardWidget(QFrame):
    """Dynamic visual card for an AI model endpoint with credentials, priority, and actions."""

    reorder_requested = pyqtSignal(object, int)  # Emits (self, direction: -1 for up, +1 for down)
    delete_requested = pyqtSignal(object)       # Emits (self)
    status_changed = pyqtSignal()
    connection_test_finished = pyqtSignal(bool, float, str)

    def __init__(self, entry: ModelEntry, parent=None) -> None:
        super().__init__(parent)
        self.entry_id = entry.id
        self.initial_entry = entry
        self._is_key_visible = False
        self._test_thread: Optional[threading.Thread] = None
        self.connection_test_finished.connect(
            self._apply_test_result, Qt.ConnectionType.QueuedConnection
        )

        self.setObjectName("ModelCard")
        self._setup_ui(entry)

    @property
    def provider_id(self) -> str:
        """Expose the model entry identifier for external use (e.g., tests)."""
        return self.entry_id

    def _setup_ui(self, entry: ModelEntry) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)

        # 1. Header: Active Checkbox, Name, Priority Badge, Controls (Up/Down/Delete)
        header = QHBoxLayout()
        header.setSpacing(8)

        self.checkbox = QCheckBox(self)
        self.checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.checkbox.setChecked(entry.enabled)
        self.checkbox.toggled.connect(lambda _: self.status_changed.emit())
        header.addWidget(self.checkbox)

        self.name_input = QLineEdit(entry.name, self)
        self.name_input.setObjectName("CardNameInput")
        self.name_input.setPlaceholderText("Model Display Name")
        font = self.name_input.font()
        font.setBold(True)
        self.name_input.setFont(font)
        header.addWidget(self.name_input, 1)

        self.badge = QLabel("[Primary]", self)
        self.badge.setObjectName("PriorityBadge")
        header.addWidget(self.badge)

        # Up arrow button
        self.up_btn = QToolButton(self)
        self.up_btn.setObjectName("CardArrowBtn")
        self.up_btn.setIcon(get_arrow_up_icon())
        self.up_btn.setToolTip("Move up in priority")
        self.up_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.up_btn.clicked.connect(lambda: self.reorder_requested.emit(self, -1))
        header.addWidget(self.up_btn)

        # Down arrow button
        self.down_btn = QToolButton(self)
        self.down_btn.setObjectName("CardArrowBtn")
        self.down_btn.setIcon(get_arrow_down_icon())
        self.down_btn.setToolTip("Move down in priority")
        self.down_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.down_btn.clicked.connect(lambda: self.reorder_requested.emit(self, 1))
        header.addWidget(self.down_btn)

        # Delete card button
        self.delete_btn = QToolButton(self)
        self.delete_btn.setObjectName("CardDeleteBtn")
        self.delete_btn.setIcon(get_trash_icon())
        self.delete_btn.setToolTip("Delete this model card")
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self))
        header.addWidget(self.delete_btn)

        layout.addLayout(header)

        # 2. Form Grid (Protocol, Base URL, Model ID, API Key, Test row)
        self.form = QGridLayout()
        self.form.setContentsMargins(0, 2, 0, 0)
        self.form.setHorizontalSpacing(10)
        self.form.setVerticalSpacing(6)

        # Protocol Selector
        lbl_proto = QLabel("Protocol:", self)
        lbl_proto.setObjectName("CardFieldLabel")
        self.form.addWidget(lbl_proto, 0, 0)

        self.proto_combo = WheelSafeComboBox(self)
        self.proto_combo.setObjectName("ModelComboBox")
        self.proto_combo.addItem("OpenAI-Compatible", "openai_compatible")
        self.proto_combo.addItem("Google Gemini", "gemini")
        if entry.protocol == "gemini":
            self.proto_combo.setCurrentIndex(1)
        else:
            self.proto_combo.setCurrentIndex(0)
        self.proto_combo.currentIndexChanged.connect(self._handle_protocol_changed)
        self.form.addWidget(self.proto_combo, 0, 1, 1, 2)

        # Base URL Row
        self.lbl_url = QLabel("Base URL:", self)
        self.lbl_url.setObjectName("CardFieldLabel")
        self.form.addWidget(self.lbl_url, 1, 0)

        self.base_url_input = QLineEdit(self)
        self.base_url_input.setObjectName("SettingsInput")
        self.base_url_input.setPlaceholderText("https://api.groq.com/openai/v1 or http://localhost:20128/v1")
        self.base_url_input.setText(entry.base_url)
        self.form.addWidget(self.base_url_input, 1, 1, 1, 2)

        # Model Selector
        lbl_model = QLabel("Model ID:", self)
        lbl_model.setObjectName("CardFieldLabel")
        self.form.addWidget(lbl_model, 2, 0)

        self.model_combo = WheelSafeComboBox(self)
        self.model_combo.setObjectName("ModelComboBox")
        self.model_combo.setEditable(True)
        self._populate_model_presets(entry.protocol, entry.model)
        self.form.addWidget(self.model_combo, 2, 1, 1, 2)

        # API Key Row
        lbl_key = QLabel("API Key:", self)
        lbl_key.setObjectName("CardFieldLabel")
        self.form.addWidget(lbl_key, 3, 0)

        key_box = QHBoxLayout()
        key_box.setSpacing(4)

        self.key_input = QLineEdit(self)
        self.key_input.setObjectName("SettingsInput")
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText("Bearer API Key (Optional for local endpoints)")
        self.key_input.setText(entry.api_key)
        key_box.addWidget(self.key_input, 1)

        self.eye_btn = QToolButton(self)
        self.eye_btn.setObjectName("EyeToggleBtn")
        self.eye_btn.setIcon(get_eye_icon(visible=False))
        self.eye_btn.setToolTip("Show / Hide Key")
        self.eye_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.eye_btn.clicked.connect(self._toggle_key_visibility)
        key_box.addWidget(self.eye_btn)

        self.form.addLayout(key_box, 3, 1, 1, 2)

        # Test Connection Row
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

        self.form.addLayout(test_box, 4, 1, 1, 2)

        layout.addLayout(self.form)
        self._handle_protocol_changed(self.proto_combo.currentIndex())

    def _populate_model_presets(self, protocol: str, selected_model: str) -> None:
        self.model_combo.clear()
        candidates: List[str] = []
        if protocol == "gemini":
            candidates = PRESETS["gemini"]["models"]
        else:
            # Combine groq, 9router, deepseek models
            for k in ["groq", "9router", "deepseek", "ollama"]:
                for m in PRESETS[k]["models"]:
                    if m not in candidates:
                        candidates.append(m)

        for m in candidates:
            self.model_combo.addItem(m)

        if selected_model:
            self.model_combo.setCurrentText(selected_model)

    def _handle_protocol_changed(self, index: int) -> None:
        is_gemini = (self.proto_combo.currentData() == "gemini")
        if is_gemini:
            self.lbl_url.hide()
            self.base_url_input.hide()
            self._populate_model_presets("gemini", self.model_combo.currentText())
        else:
            self.lbl_url.show()
            self.base_url_input.show()
            self._populate_model_presets("openai_compatible", self.model_combo.currentText())

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
        self.test_result.setToolTip("")
        self.test_result.setStyleSheet("color: #f9e2af;")

        protocol = self.proto_combo.currentData()
        model = self.model_combo.currentText().strip()
        api_key = self.key_input.text().strip()
        base_url = self.base_url_input.text().strip() if protocol != "gemini" else ""

        def _worker():
            try:
                success, latency, msg = APIClient.test_provider_connection(
                    provider_type=protocol,
                    model=model,
                    api_key=api_key,
                    base_url=base_url,
                    timeout=8,
                )
            except Exception as exc:
                success, latency, msg = False, 0.0, str(exc)

            try:
                self.connection_test_finished.emit(success, latency, msg)
            except RuntimeError:
                # The card may have been deleted while the request was running.
                pass

        self._test_thread = threading.Thread(target=_worker, daemon=True)
        self._test_thread.start()

    def _apply_test_result(self, success: bool, latency: float, msg: str) -> None:
        """Display the worker result on the GUI thread and allow another test."""
        self._test_thread = None
        self.test_btn.setEnabled(True)
        self.test_result.setToolTip(msg)
        if success:
            self.test_result.setText(f"✓ {latency}s ({msg})")
            self.test_result.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        else:
            snippet = msg[:40] + "..." if len(msg) > 40 else msg
            self.test_result.setText(f"✗ {snippet}")
            self.test_result.setStyleSheet("color: #f38ba8;")

    def to_model_entry(self) -> ModelEntry:
        """Convert current form inputs into a ModelEntry object."""
        protocol = self.proto_combo.currentData() or "openai_compatible"
        base_url = self.base_url_input.text().strip() if protocol != "gemini" else ""
        return ModelEntry(
            id=self.entry_id,
            name=self.name_input.text().strip() or "Unnamed Model",
            protocol=protocol,
            base_url=base_url,
            model=self.model_combo.currentText().strip(),
            api_key=self.key_input.text().strip(),
            enabled=self.checkbox.isChecked(),
            temperature=self.initial_entry.temperature,
            max_tokens=self.initial_entry.max_tokens,
        )

    def set_priority_badge(self, text: str, is_active: bool) -> None:
        self.badge.setText(text)
        if not is_active:
            self.badge.setStyleSheet("color: #6c7086; background: rgba(108, 112, 134, 0.15);")
        elif "Primary" in text:
            self.badge.setStyleSheet("color: #a6e3a1; background: rgba(166, 227, 161, 0.15);")
        else:
            self.badge.setStyleSheet("color: #89b4fa; background: rgba(137, 180, 250, 0.15);")

    def set_delete_enabled(self, enabled: bool) -> None:
        self.delete_btn.setEnabled(enabled)
        if not enabled:
            self.delete_btn.setToolTip("Cannot delete the only remaining model card.")
        else:
            self.delete_btn.setToolTip("Delete this model card")


class SettingsView(QFrame):
    """Full-featured Settings HUD view with dynamic creatable and deletable model cards."""

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

        # 1. Header: Title, Subtitle, Close Button
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

        subtitle = QLabel("Create, test, reorder, or delete AI model endpoints.", self)
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

        # 2. Scroll Area for dynamic cards list
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

        self.scroll_area.setWidget(self.cards_container)
        main_layout.addWidget(self.scroll_area, 1)

        # 3. Add Card Action Bar
        add_bar = QHBoxLayout()
        add_bar.setSpacing(8)

        lbl_preset = QLabel("Preset Template:", self)
        lbl_preset.setObjectName("CardFieldLabel")
        add_bar.addWidget(lbl_preset)

        self.preset_combo = WheelSafeComboBox(self)
        self.preset_combo.setObjectName("ModelComboBox")
        self.preset_combo.addItem("Groq Cloud (LPU Instant)", "groq")
        self.preset_combo.addItem("9Router (Local Gateway)", "9router")
        self.preset_combo.addItem("Google Gemini", "gemini")
        self.preset_combo.addItem("DeepSeek API", "deepseek")
        self.preset_combo.addItem("Ollama (Local)", "ollama")
        self.preset_combo.addItem("Custom Endpoint", "custom")
        add_bar.addWidget(self.preset_combo, 1)

        self.add_card_btn = QPushButton("Add Model Card", self)
        self.add_card_btn.setObjectName("AddCardBtn")
        self.add_card_btn.setIcon(get_plus_icon())
        self.add_card_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_card_btn.clicked.connect(self._handle_add_card)
        add_bar.addWidget(self.add_card_btn)

        main_layout.addLayout(add_bar)

        # 4. Footer Actions (Status, Cancel, Save)
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

        self.save_btn = QPushButton("Apply", self)
        self.save_btn.setObjectName("SettingsSaveBtn")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.clicked.connect(self._handle_save)
        footer.addWidget(self.save_btn)

        main_layout.addLayout(footer)

    def load_from_config(self, config: Config) -> None:
        """Populate model cards from config.models or models.json."""
        self.config = config

        # Clear existing cards
        while self.cards_layout.count() > 0:
            item = self.cards_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.cards.clear()

        # Load entries
        entries = list(config.models) if config.models else load_models_config(config.config_dir)

        for entry in entries:
            self._create_and_append_card(entry)

        self._rebuild_layout_and_badges()
        self.footer_status.setText("")

    def _create_and_append_card(self, entry: ModelEntry) -> ModelCardWidget:
        card = ModelCardWidget(entry, parent=self.cards_container)
        card.reorder_requested.connect(self._handle_card_reorder)
        card.delete_requested.connect(self._handle_card_delete)
        card.status_changed.connect(self._refresh_priority_badges)
        self.cards.append(card)
        return card

    def _handle_add_card(self) -> None:
        preset_key = self.preset_combo.currentData() or "custom"
        new_entry = create_entry_from_preset(preset_key)
        card = self._create_and_append_card(new_entry)
        self._rebuild_layout_and_badges()

        # Scroll to newly added card
        QTimer.singleShot(50, lambda: self.scroll_area.ensureWidgetVisible(card))

    def _handle_card_delete(self, card: ModelCardWidget) -> None:
        if len(self.cards) <= 1:
            return

        if card in self.cards:
            self.cards.remove(card)
            card.setParent(None)
            card.deleteLater()
            self._rebuild_layout_and_badges()

    def _handle_card_reorder(self, card: ModelCardWidget, direction: int) -> None:
        idx = self.cards.index(card)
        new_idx = idx + direction
        if 0 <= new_idx < len(self.cards):
            self.cards[idx], self.cards[new_idx] = self.cards[new_idx], self.cards[idx]
            self._rebuild_layout_and_badges()

    def _rebuild_layout_and_badges(self) -> None:
        # Clear layout items without deleting widgets
        while self.cards_layout.count() > 0:
            item = self.cards_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)

        for card in self.cards:
            self.cards_layout.addWidget(card)
        self.cards_layout.addStretch(1)

        # Enforce minimum 1 card rule
        can_delete = len(self.cards) > 1
        for card in self.cards:
            card.set_delete_enabled(can_delete)

        self._refresh_priority_badges()

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
        """Persist model list to models.json, sync config.env, and hot-reload."""
        entries = [c.to_model_entry() for c in self.cards]

        try:
            # 1. Save to models.json
            models_file = save_models_config(entries, self.config.config_dir)

            # 2. Sync primary/fallback to config.env for backward compatibility
            enabled_entries = [e for e in entries if e.enabled]
            env_updates: Dict[str, str] = {
                "PROVIDER_ORDER": ",".join([e.id for e in enabled_entries]),
            }
            # Also extract groq / gemini keys if present
            for e in entries:
                if "groq" in e.id or "groq" in e.name.lower():
                    env_updates["GROQ_MODEL"] = e.model
                    if e.api_key:
                        env_updates["GROQ_API_KEY"] = e.api_key
                    if e.base_url:
                        env_updates["GROQ_BASE_URL"] = e.base_url
                elif e.protocol == "gemini" or "gemini" in e.id:
                    env_updates["GEMINI_MODEL"] = e.model
                    if e.api_key:
                        env_updates["GEMINI_API_KEY"] = e.api_key
                elif "9router" in e.id or "custom" in e.id:
                    env_updates["CUSTOM_OPENAI_MODEL"] = e.model
                    env_updates["CUSTOM_OPENAI_BASE_URL"] = e.base_url
                    if e.api_key:
                        env_updates["CUSTOM_OPENAI_API_KEY"] = e.api_key

            save_config_file(env_updates)

            # 3. Hot-reload Config in memory
            new_config = load_config(script_dir=self.config.script_dir)
            self.config = new_config

            self.footer_status.setText(f"✓ Saved to {models_file.name}")
            self.footer_status.setStyleSheet("color: #a6e3a1; font-weight: bold;")
            self.saved.emit(new_config)
        except Exception as e:
            self.footer_status.setText(f"Error saving: {e}")
            self.footer_status.setStyleSheet("color: #f38ba8;")
