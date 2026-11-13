"""Provider connections, catalog discovery, and saved model profile editors."""

from __future__ import annotations

import copy
import threading
import time
from dataclasses import asdict, replace
from datetime import datetime, timezone

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QLayout, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QRadioButton, QScrollArea, QSpinBox, QToolButton, QVBoxLayout, QWidget,
)

from core.config import Config
from core.provider_api import CAPABILITIES, default_profile, discover_models, generate_text
from core.provider_config import (
    PROVIDER_PRESETS, ModelProfile, Provider, create_provider, migrate_models, new_id,
    save_providers, validate_provider,
)
from .icons import get_arrow_down_icon, get_arrow_up_icon, get_exit_icon, get_plus_icon
from .legacy_settings_view import WheelSafeComboBox


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout():
            clear_layout(item.layout())


def action(text, callback, parent=None):
    button = QPushButton(text, parent)
    button.clicked.connect(callback)
    return button


class SurfaceDialog(QDialog):
    """Draw rounded dialog content over a transparent top-level window."""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        surface = QFrame(self)
        surface.setObjectName("ProviderDialog")
        outer.addWidget(surface)
        self.body = QVBoxLayout(surface)
        self.body.setContentsMargins(22, 20, 22, 20)
        self.body.setSpacing(14)
        self.body.addWidget(QLabel(title))
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setObjectName("ProviderError")

    def footer(self, accept_text="Apply"):
        self.body.addWidget(self.error_label)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(accept_text)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.body.addWidget(buttons)


class ModelEditor(SurfaceDialog):
    """Search cached provider models or enter an ID manually, then save a profile."""

    def __init__(self, provider, profile=None, parent=None):
        super().__init__("Model Settings" if profile else "Add Model", parent)
        self.provider = provider
        self.original = profile
        self.result_profile = None
        self.resize(620, 630)
        self.body.addWidget(QLabel(provider.name))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search provider models...")
        self.body.addWidget(self.search)
        self.catalog_list = QListWidget()
        self.catalog_list.setMinimumHeight(120)
        self.body.addWidget(self.catalog_list)
        for entry in provider.catalog:
            info = entry.get("metadata", {})
            suffix = "Text generation not supported" if info.get("text_output") is False else "Capabilities unverified" if not info else "Text model"
            item = QListWidgetItem(f"{entry.get('name', entry['id'])}\n{entry['id']} · {suffix}")
            item.setData(Qt.ItemDataRole.UserRole, entry["id"])
            if info.get("text_output") is False:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.catalog_list.addItem(item)
        self.search.textChanged.connect(self._filter)
        self.catalog_list.currentItemChanged.connect(self._selected)
        if not provider.catalog:
            self.body.addWidget(QLabel("No cached catalog. Connect/Refresh in the provider card, or enter a model ID."))
        form = QFormLayout()
        self.model_id = QLineEdit(profile.model if profile else "")
        self.model_id.setPlaceholderText("Select above or enter model ID manually")
        self.name = QLineEdit(profile.name if profile else "")
        self.reasoning = WheelSafeComboBox()
        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(-0.01, 2)
        self.temperature.setSpecialValueText("Provider default")
        self.temperature.setSingleStep(0.1)
        self.output_limit = QSpinBox()
        self.output_limit.setRange(0, 2_000_000)
        self.output_limit.setSpecialValueText("Provider default")
        self.token_parameter = WheelSafeComboBox()
        self.token_parameter.addItems(["max_tokens", "max_completion_tokens"])
        self.token_parameter.setToolTip("Advanced: parameter used by this Chat Completions endpoint")
        self.capability_label = QLabel()
        self.capability_label.setWordWrap(True)
        form.addRow("Model ID", self.model_id)
        form.addRow("Display name", self.name)
        form.addRow("Reasoning effort", self.reasoning)
        form.addRow("Temperature", self.temperature)
        form.addRow("Output limit", self.output_limit)
        if provider.protocol == "openai_compatible":
            form.addRow("Advanced token parameter", self.token_parameter)
        self.body.addLayout(form)
        self.body.addWidget(self.capability_label)
        self.model_id.textChanged.connect(self._capabilities)
        self.reasoning.currentIndexChanged.connect(self._temperature_state)
        self._capabilities(self.model_id.text())
        if profile:
            self.reasoning.setCurrentText(profile.reasoning.capitalize() if profile.reasoning else "Provider default")
            self.temperature.setValue(profile.temperature if profile.temperature is not None else -0.01)
            self.output_limit.setValue(profile.max_tokens or 0)
            self.token_parameter.setCurrentText(profile.token_parameter)
        else:
            self.temperature.setValue(-0.01)
        self.footer("Save Model" if profile else "Add Model")

    def _filter(self, text):
        for index in range(self.catalog_list.count()):
            item = self.catalog_list.item(index)
            item.setHidden(text.lower() not in item.text().lower())

    def _selected(self, item, previous):
        if item:
            self.model_id.setText(item.data(Qt.ItemDataRole.UserRole))

    def _capabilities(self, model_id):
        info = CAPABILITIES.get(model_id, {})
        self.reasoning.blockSignals(True)
        self.reasoning.clear()
        self.reasoning.addItem("Provider default", "")
        efforts = [] if self.provider.protocol == "gemini" else info.get("reasoning", ["none", "low", "medium", "high", "xhigh", "max"])
        for effort in efforts:
            self.reasoning.addItem(effort.capitalize(), effort)
        self.reasoning.setCurrentText(info.get("default_reasoning", "").capitalize() or "Provider default")
        self.reasoning.blockSignals(False)
        self.token_parameter.setCurrentText(info.get("token_parameter", "max_tokens"))
        self.capability_label.setText("Verified model settings loaded." if info else "Unknown capabilities: optional parameters are omitted by default. Test any manual overrides.")
        if not self.original:
            self.name.setText(info.get("name", model_id))
        self._temperature_state()

    def _temperature_state(self):
        info = CAPABILITIES.get(self.model_id.text(), {})
        allowed = info.get("temperature") is not False and self.reasoning.currentData() in ("", "none", None)
        self.temperature.setEnabled(allowed)
        if not allowed:
            self.temperature.setValue(-0.01)

    def accept(self):
        try:
            self.result_profile = ModelProfile.from_dict({
                "id": self.original.id if self.original else new_id(),
                "name": self.name.text().strip(), "model": self.model_id.text().strip(),
                "reasoning": self.reasoning.currentData() or "",
                "temperature": self.temperature.value() if self.temperature.isEnabled() and self.temperature.value() >= 0 else None,
                "max_tokens": self.output_limit.value() or None,
                "token_parameter": self.token_parameter.currentText(),
            })
        except ValueError as exc:
            self.error_label.setText(str(exc))
            return
        super().accept()


class ProviderCard(QFrame):
    """A draft connection and its saved models; network results are queued to Qt."""

    changed = pyqtSignal()
    reorder_requested = pyqtSignal(object, int)
    delete_requested = pyqtSignal(object)
    network_finished = pyqtSignal(int, object, str)

    def __init__(self, provider, parent=None):
        super().__init__(parent)
        self.provider = provider
        self.provider_id = provider.id
        self.setObjectName("ProviderCard")
        self._generation = 0
        self._busy = False
        self.network_finished.connect(self._network_result, Qt.ConnectionType.QueuedConnection)
        body = QVBoxLayout(self)
        body.setContentsMargins(16, 14, 16, 14)
        header = QHBoxLayout()
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(provider.enabled)
        self.checkbox.toggled.connect(self._enabled)
        self.name_input = QLineEdit(provider.name)
        self.name_input.setObjectName("CardNameInput")
        self.name_input.textEdited.connect(self._rename)
        self.badge = QLabel()
        header.addWidget(self.checkbox)
        header.addWidget(self.name_input, 1)
        header.addWidget(self.badge)
        body.addLayout(header)
        actions = QHBoxLayout()
        self.up_btn = QToolButton()
        self.up_btn.setIcon(get_arrow_up_icon())
        self.up_btn.setToolTip("Move provider up in fallback order; choose primary in the input bar")
        self.up_btn.clicked.connect(lambda: self.reorder_requested.emit(self, -1))
        self.down_btn = QToolButton()
        self.down_btn.setIcon(get_arrow_down_icon())
        self.down_btn.setToolTip("Move provider down in fallback order; choose primary in the input bar")
        self.down_btn.clicked.connect(lambda: self.reorder_requested.emit(self, 1))
        self.collapse_btn = action("Collapse", self._collapse)
        actions.addWidget(self.up_btn)
        actions.addWidget(self.down_btn)
        actions.addWidget(self.collapse_btn)
        actions.addStretch()
        actions.addWidget(action("Remove Provider", lambda: self.delete_requested.emit(self)))
        body.addLayout(actions)
        self.summary = QLabel()
        body.addWidget(self.summary)
        self.details = QWidget()
        details = QVBoxLayout(self.details)
        details.setContentsMargins(0, 6, 0, 0)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.proto_combo = WheelSafeComboBox()
        for name, value in (("OpenAI Chat Completions", "openai_compatible"), ("OpenAI Responses", "openai_responses"), ("Google Gemini Native", "gemini")):
            self.proto_combo.addItem(name, value)
        self.proto_combo.setCurrentIndex(self.proto_combo.findData(provider.protocol))
        self.base_url_input = QLineEdit(provider.base_url)
        self.key_input = QLineEdit(provider.api_key)
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText("API key (optional for localhost)")
        key_row = QHBoxLayout()
        key_row.addWidget(self.key_input)
        self.reveal_btn = action("Show", self._reveal)
        key_row.addWidget(self.reveal_btn)
        form.addRow("Protocol", self.proto_combo)
        form.addRow("API root URL", self.base_url_input)
        form.addRow("API key", key_row)
        details.addLayout(form)
        self.proto_combo.currentIndexChanged.connect(self._connection_changed)
        self.base_url_input.textEdited.connect(self._connection_changed)
        self.key_input.textEdited.connect(self._connection_changed)
        connection_actions = QHBoxLayout()
        self.connect_btn = action("Connect / Refresh Models", self.refresh_catalog)
        connection_actions.addWidget(self.connect_btn)
        self.connection_status = QLabel("Not verified")
        self.connection_status.setWordWrap(True)
        details.addLayout(connection_actions)
        details.addWidget(self.connection_status)
        self.catalog_status = QLabel()
        self.catalog_status.setWordWrap(True)
        details.addWidget(self.catalog_status)
        details.addWidget(QLabel("My Models — select one active configuration"))
        self.models_layout = QVBoxLayout()
        details.addLayout(self.models_layout)
        details.addWidget(action("+ Add Model", self.add_model))
        self.test_result = QLabel()
        self.test_result.setWordWrap(True)
        details.addWidget(self.test_result)
        body.addWidget(self.details)
        self._render_models()

    def _enabled(self, value):
        self.provider.enabled = value
        self.changed.emit()

    def _rename(self, value):
        self.provider.name = value.strip()
        self.changed.emit()

    def _reveal(self):
        hidden = self.key_input.echoMode() == QLineEdit.EchoMode.Password
        self.key_input.setEchoMode(QLineEdit.EchoMode.Normal if hidden else QLineEdit.EchoMode.Password)
        self.reveal_btn.setText("Hide" if hidden else "Show")

    def _collapse(self):
        self.details.setVisible(not self.details.isVisible())
        self.collapse_btn.setText("Collapse" if self.details.isVisible() else "Expand")

    def _connection_changed(self, *args):
        self._generation += 1
        self._busy = False
        self.connect_btn.setEnabled(True)
        self.provider.protocol = self.proto_combo.currentData()
        self.provider.base_url = self.base_url_input.text().strip()
        self.provider.api_key = self.key_input.text().strip()
        self.provider.catalog = []
        self.provider.catalog_updated_at = ""
        self.connection_status.setText("Connection changed — reconnect")
        self.test_result.clear()
        self._catalog_label()

    def _catalog_label(self):
        stamp = self.provider.catalog_updated_at or "never"
        self.catalog_status.setText(f"{len(self.provider.catalog)} cached models · Updated: {stamp}")

    def refresh_catalog(self):
        if self._busy:
            return
        self._run_network("catalog")

    def _run_network(self, kind, profile=None):
        try:
            validate_provider(self.provider)
        except ValueError as exc:
            self.connection_status.setText(str(exc))
            return
        if not self.provider.authenticated:
            self.connection_status.setText("Missing API key.")
            return
        self._generation += 1
        generation = self._generation
        snapshot = copy.deepcopy(self.provider)
        self._busy = True
        self.connect_btn.setEnabled(False)
        (self.connection_status if kind == "catalog" else self.test_result).setText("Loading models..." if kind == "catalog" else "Testing...")

        def work():
            try:
                started = time.monotonic()
                if kind == "catalog":
                    result = {"catalog": discover_models(snapshot)}
                else:
                    generate_text(snapshot, profile, "Reply briefly.", "Reply with OK.", timeout=30)
                    result = {"test": f"✓ {profile.name}: {time.monotonic() - started:.2f}s"}
                error = ""
            except Exception as exc:
                result = {}
                error = str(exc).replace(snapshot.api_key, "[redacted]") if snapshot.api_key else str(exc)
            try:
                self.network_finished.emit(generation, result, error)
            except RuntimeError:
                pass

        self._thread = threading.Thread(target=work, daemon=True)
        self._thread.start()

    def _network_result(self, generation, result, error):
        if generation != self._generation:
            return
        self._busy = False
        self.connect_btn.setEnabled(True)
        if error:
            self.connection_status.setText("Request failed; previous catalog retained.")
            self.connection_status.setToolTip(error)
            self.test_result.setText(error)
            return
        if "catalog" in result:
            self.provider.catalog = result["catalog"]
            self.provider.catalog_updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self.connection_status.setText("Connected · Catalog loaded (models not individually tested)")
            self._catalog_label()
            self._render_models()
        else:
            self.test_result.setText(result["test"])

    def add_model(self):
        dialog = ModelEditor(self.provider, parent=self.window())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.provider.models.append(dialog.result_profile)
            if not self.provider.active_model_id:
                self.provider.active_model_id = dialog.result_profile.id
            self._render_models()
            self.changed.emit()

    def _edit_model(self, profile):
        dialog = ModelEditor(self.provider, profile, self.window())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.provider.models = [dialog.result_profile if m.id == profile.id else m for m in self.provider.models]
            self._render_models()
            self.changed.emit()

    def _duplicate(self, profile):
        self.provider.models.append(replace(profile, id=new_id(), name=profile.name + " Copy"))
        self._render_models()
        self.changed.emit()

    def _remove_model(self, profile):
        if profile.id == self.provider.active_model_id and len(self.provider.models) > 1:
            self.test_result.setText("Select another active model before removing this configuration.")
            return
        self.provider.models = [m for m in self.provider.models if m.id != profile.id]
        if not self.provider.models:
            self.provider.active_model_id = ""
        self._render_models()
        self.changed.emit()

    def _activate(self, profile):
        self.provider.active_model_id = profile.id
        self._render_models()
        self.changed.emit()

    def _render_models(self):
        clear_layout(self.models_layout)
        if hasattr(self, "radio_group"):
            self.radio_group.deleteLater()
        self.radio_group = QButtonGroup(self)
        for profile in self.provider.models:
            model_frame = QFrame()
            model_frame.setObjectName("SavedModel")
            layout = QVBoxLayout(model_frame)
            radio = QRadioButton(profile.name)
            radio.setChecked(profile.id == self.provider.active_model_id)
            self.radio_group.addButton(radio)
            radio.clicked.connect(lambda checked, m=profile: self._activate(m))
            layout.addWidget(radio)
            available = {item["id"] for item in self.provider.catalog}
            status = " · Not in latest catalog" if self.provider.catalog_updated_at and profile.model not in available else ""
            detail = QLabel(f"{profile.model} · {profile.reasoning or 'Provider defaults'}{status}")
            detail.setWordWrap(True)
            layout.addWidget(detail)
            buttons = QHBoxLayout()
            buttons.addWidget(action("Test", lambda checked=False, m=profile: self.test_model(m)))
            buttons.addWidget(action("Settings", lambda checked=False, m=profile: self._edit_model(m)))
            buttons.addWidget(action("Duplicate", lambda checked=False, m=profile: self._duplicate(m)))
            buttons.addStretch()
            buttons.addWidget(action("Remove", lambda checked=False, m=profile: self._remove_model(m)))
            layout.addLayout(buttons)
            self.models_layout.addWidget(model_frame)
        self.summary.setText("Active: " + (self.provider.active_model.name if self.provider.active_model else "No model selected"))
        self._catalog_label()

    def test_model(self, profile):
        if not self._busy:
            self._run_network("test", copy.deepcopy(profile))


class SettingsView(QFrame):
    """A draft provider editor; Apply is the only configuration persistence action."""

    saved = pyqtSignal(object)
    closed = pyqtSignal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config_owner = parent
        self.setObjectName("SettingsView")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setAutoFillBackground(False)
        self.cards = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 14)
        header = QHBoxLayout()
        title = QLabel("Providers & Models")
        title.setObjectName("SettingsHeaderTitle")
        header.addWidget(title, 1)
        close = QToolButton()
        close.setIcon(get_exit_icon())
        close.clicked.connect(self.closed.emit)
        header.addWidget(close)
        outer.addLayout(header)
        subtitle = QLabel("Connect once. Save models. Select one active configuration per provider.")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.scroll_area.setWidget(self.cards_container)
        outer.addWidget(self.scroll_area, 1)
        add = QHBoxLayout()
        self.preset_combo = WheelSafeComboBox()
        for key, preset in PROVIDER_PRESETS.items():
            self.preset_combo.addItem(preset["name"], key)
        add.addWidget(self.preset_combo, 1)
        self.add_card_btn = action("Add Provider", self._handle_add_card)
        self.add_card_btn.setIcon(get_plus_icon())
        add.addWidget(self.add_card_btn)
        outer.addLayout(add)
        footer = QHBoxLayout()
        self.footer_status = QLabel()
        self.footer_status.setWordWrap(True)
        footer.addWidget(self.footer_status, 1)
        self.cancel_btn = action("Cancel", self.closed.emit)
        self.save_btn = action("Apply", self._handle_save)
        self.save_btn.setObjectName("SettingsSaveBtn")
        footer.addWidget(self.cancel_btn)
        footer.addWidget(self.save_btn)
        outer.addLayout(footer)
        self.load_from_config(config)

    def load_from_config(self, config):
        self.config = config
        self.selected_provider_id = config.selected_provider_id
        clear_layout(self.cards_layout)
        self.cards = []
        providers = copy.deepcopy(list(config.providers) if config.providers is not None else migrate_models(list(config.models)))
        for provider in providers:
            self._append(provider)
        self._rebuild()
        self.footer_status.clear()

    def _append(self, provider):
        card = ProviderCard(provider, self.cards_container)
        card.changed.connect(self._refresh_priority_badges)
        card.reorder_requested.connect(self._reorder)
        card.delete_requested.connect(self._delete)
        self.cards.append(card)
        return card

    def _handle_add_card(self):
        card = self._append(create_provider(self.preset_combo.currentData()))
        self._rebuild()
        self.scroll_area.ensureWidgetVisible(card)

    def _delete(self, card):
        self.cards.remove(card)
        card.deleteLater()
        self._rebuild()

    def _reorder(self, card, direction):
        index = self.cards.index(card)
        other = index + direction
        if 0 <= other < len(self.cards):
            self.cards[index], self.cards[other] = self.cards[other], self.cards[index]
            self._rebuild()

    def _rebuild(self):
        while self.cards_layout.count():
            self.cards_layout.takeAt(0)
        for index, card in enumerate(self.cards):
            self.cards_layout.addWidget(card)
            card.up_btn.setEnabled(index > 0)
            card.down_btn.setEnabled(index < len(self.cards) - 1)
        self.cards_layout.addStretch()
        self._refresh_priority_badges()

    def _refresh_priority_badges(self):
        enabled = [c for c in self.cards if c.provider.enabled]
        primary = next((c for c in enabled if c.provider.id == self.selected_provider_id), enabled[0] if enabled else None)
        rank = 1
        for card in self.cards:
            if not card.provider.enabled:
                text = "[Disabled]"
            elif card is primary:
                text = "[Primary]"
            else:
                text = f"[Fallback {rank}]"
                rank += 1
            card.badge.setText(text)

    def _handle_save(self):
        try:
            current = getattr(self.config_owner, "config", self.config)
            if current is not self.config:
                raise ValueError("Settings changed in another card. Close and reopen Settings before applying.")
            if any(c._busy for c in self.cards):
                raise ValueError("Wait for connection/model tests to finish before applying.")
            providers = [copy.deepcopy(card.provider) for card in self.cards]
            selected = next((p.id for p in providers if p.id == self.selected_provider_id and p.enabled), "")
            selected = selected or next((p.id for p in providers if p.enabled), "")
            save_providers(providers, self.config.config_dir, selected)
            new_config = replace(self.config, providers=tuple(providers), selected_provider_id=selected)
            self.config = new_config
            self.saved.emit(new_config)
        except (ValueError, OSError) as exc:
            self.footer_status.setText(str(exc))
