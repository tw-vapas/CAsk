"""Provider connections, catalog discovery, and saved model profile editors."""

from __future__ import annotations

import copy
import threading
import time
from dataclasses import replace
from datetime import datetime, timezone

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QDoubleSpinBox, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QLayout, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QRadioButton, QScrollArea, QSpinBox, QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)

from core.config import Config
from core.provider_api import CAPABILITIES, discover_models, generate_text
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


def label(text, role="SettingsDescription"):
    widget = QLabel(text)
    widget.setObjectName(role)
    widget.setWordWrap(True)
    return widget


def confirmation(title, description, callback, cancel, removal):
    frame = QFrame()
    frame.setObjectName("InlineConfirmation")
    body = QVBoxLayout(frame)
    body.addWidget(label(title, "SettingsHeading"))
    body.addWidget(label(description))
    buttons = QHBoxLayout()
    buttons.addStretch()
    buttons.addWidget(action("Cancel", cancel))
    remove = action(removal, callback)
    remove.setObjectName("SettingsDanger")
    buttons.addWidget(remove)
    body.addLayout(buttons)
    return frame


class ModelEditor(QWidget):
    """Embedded catalog/configuration pages; never creates a native dialog."""

    saved = pyqtSignal(object)
    cancelled = pyqtSignal()
    close_requested = pyqtSignal()

    def __init__(self, provider, profile=None, parent=None):
        super().__init__(parent)
        self.provider = provider
        self.original = profile
        self.result_profile = None
        body = QVBoxLayout(self)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(14)
        header = QHBoxLayout()
        self.back_btn = action("← Back", self.back)
        self.back_btn.setObjectName("SettingsGhost")
        header.addWidget(self.back_btn)
        self.title = label("", "SettingsHeaderTitle")
        header.addWidget(self.title, 1)
        header.addWidget(action("×", self.close_requested.emit))
        body.addLayout(header)
        self.subtitle = label("")
        body.addWidget(self.subtitle)
        self.pages = QStackedWidget()
        body.addWidget(self.pages, 1)
        self.picker = QWidget()
        picker = QVBoxLayout(self.picker)
        picker.setContentsMargins(0, 0, 0, 0)
        picker.setSpacing(14)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search available models...")
        picker.addWidget(self.search)
        picker.addWidget(label(f"Provider catalog · {len(provider.catalog)} models · Updated: {provider.catalog_updated_at or 'never'}"))
        self.catalog_list = QListWidget()
        picker.addWidget(self.catalog_list, 1)
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
        picker.addWidget(label("Enter model ID manually"))
        self.model_id = QLineEdit(profile.model if profile else "")
        self.model_id.setPlaceholderText("Select above or enter model ID manually")
        picker.addWidget(self.model_id)
        self.pages.addWidget(self.picker)
        self.configuration_scroll = QScrollArea()
        self.configuration_scroll.setWidgetResizable(True)
        self.configuration_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.configuration_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        configuration = QWidget()
        form_body = QVBoxLayout(configuration)
        form_body.setContentsMargins(0, 0, 0, 0)
        form_body.setSpacing(14)
        self.identity = label("", "ModelIdentity")
        form_body.addWidget(self.identity)
        self.name = QLineEdit(profile.name if profile else "")
        self.reasoning = WheelSafeComboBox()
        form_body.addWidget(label("Display name"))
        form_body.addWidget(self.name)
        form_body.addWidget(label("Reasoning effort"))
        form_body.addWidget(self.reasoning)
        form_body.addWidget(label("Choose how much reasoning this model uses."))
        self.advanced_btn = action("▸ Advanced", self._toggle_advanced)
        self.advanced_btn.setObjectName("SettingsGhost")
        form_body.addWidget(self.advanced_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.advanced = QWidget()
        form = QFormLayout(self.advanced)
        form.setContentsMargins(0, 0, 0, 0)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(-0.01, 2)
        self.temperature.setSpecialValueText("Provider default")
        self.temperature.setSingleStep(0.1)
        self.output_limit = QSpinBox()
        self.output_limit.setRange(0, 2_000_000)
        self.output_limit.setSpecialValueText("Provider default")
        self.token_parameter = WheelSafeComboBox()
        self.token_parameter.addItems(["max_tokens", "max_completion_tokens"])
        self.token_parameter.setToolTip("Parameter used by this Chat Completions endpoint")
        form.addRow("Output limit", self.output_limit)
        form.addRow("Temperature", self.temperature)
        if provider.protocol == "openai_compatible":
            form.addRow("Token parameter", self.token_parameter)
        self.capability_label = label("")
        form.addRow(self.capability_label)
        form_body.addWidget(self.advanced)
        self.advanced.hide()
        form_body.addStretch()
        self.configuration_scroll.setWidget(configuration)
        self.pages.addWidget(self.configuration_scroll)
        self.error_label = label("", "ProviderError")
        body.addWidget(self.error_label)
        self.hint = label("Return here at any time. Changes are saved after Apply on the provider page.")
        body.addWidget(self.hint)
        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(action("Cancel", self.cancelled.emit))
        self.continue_btn = action("Continue →", self.continue_to_configuration)
        self.continue_btn.setObjectName("SettingsSaveBtn")
        footer.addWidget(self.continue_btn)
        self.save_btn = action("Save Model" if profile else "Add Model", self.accept)
        self.save_btn.setObjectName("SettingsSaveBtn")
        footer.addWidget(self.save_btn)
        body.addLayout(footer)
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
        self._show_page(1 if profile else 0)

    def _toggle_advanced(self):
        expanded = self.advanced.isHidden()
        self.advanced.setVisible(expanded)
        self.advanced_btn.setText("▾ Advanced" if expanded else "▸ Advanced")

    def _show_page(self, index):
        self.pages.setCurrentIndex(index)
        self.title.setText("Edit Model" if self.original else "Configure Model" if index else "Add Model")
        self.subtitle.setText(self.provider.name + (f" · {self.original.name}" if self.original else f" · Step {index + 1} of 2 — " + ("Configure model" if index else "Choose a model")))
        self.continue_btn.setVisible(not index)
        self.save_btn.setVisible(bool(index))
        self.hint.setVisible(bool(index))
        self.error_label.clear()

    def continue_to_configuration(self):
        if not self.model_id.text().strip():
            self.error_label.setText("Select a model or enter a model ID.")
            return
        entry = next((e for e in self.provider.catalog if e["id"] == self.model_id.text().strip()), {})
        if entry.get("metadata", {}).get("text_output") is False:
            self.error_label.setText("This model does not support text generation.")
            return
        self._show_page(1)

    def back(self):
        if self.pages.currentIndex() and not self.original:
            self._show_page(0)
        else:
            self.cancelled.emit()

    def _filter(self, text):
        for index in range(self.catalog_list.count()):
            item = self.catalog_list.item(index)
            item.setHidden(text.lower() not in item.text().lower())

    def _selected(self, item, previous):
        if item:
            self.model_id.setText(item.data(Qt.ItemDataRole.UserRole))

    def _capabilities(self, model_id):
        self.identity.setText(CAPABILITIES.get(model_id, {}).get("name", model_id) + "\n" + model_id if model_id else "Choose a model")
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
        self.saved.emit(self.result_profile)


class ProviderCard(QFrame):
    """A draft connection and its saved models; network results are queued to Qt."""

    changed = pyqtSignal()
    reorder_requested = pyqtSignal(object, int)
    delete_requested = pyqtSignal(object)
    expansion_requested = pyqtSignal(object)
    editor_requested = pyqtSignal(object, object)
    network_finished = pyqtSignal(int, object, str)

    def __init__(self, provider, parent=None):
        super().__init__(parent)
        self.provider = provider
        self.provider_id = provider.id
        self.setObjectName("ProviderCard")
        self._generation = 0
        self._busy = False
        self._expanded = False
        self._confirm_model_id = None
        self._actions_model_id = None
        self.network_finished.connect(self._network_result, Qt.ConnectionType.QueuedConnection)
        body = QVBoxLayout(self)
        body.setContentsMargins(16, 14, 16, 14)
        header = QHBoxLayout()
        self.collapse_btn = action("▸  " + provider.name, lambda: self.expansion_requested.emit(self))
        self.collapse_btn.setObjectName("ProviderName")
        header.addWidget(self.collapse_btn, 1)
        self.badge = label("", "SettingsPrimaryBadge")
        header.addWidget(self.badge)
        self.connection_badge = label("Cached" if provider.catalog_updated_at else "Not verified", "SettingsDescription")
        header.addWidget(self.connection_badge)
        self.menu_btn = action("···", lambda: self.provider_actions.setVisible(self.provider_actions.isHidden()))
        self.menu_btn.setObjectName("SettingsGhost")
        header.addWidget(self.menu_btn)
        body.addLayout(header)
        self.summary = label("")
        body.addWidget(self.summary)
        self.provider_actions = QWidget()
        actions = QHBoxLayout(self.provider_actions)
        actions.setContentsMargins(0, 0, 0, 0)
        self.checkbox = QCheckBox("Enabled")
        self.checkbox.setChecked(provider.enabled)
        self.checkbox.toggled.connect(self._enabled)
        actions.addWidget(self.checkbox)
        self.up_btn = QToolButton()
        self.up_btn.setIcon(get_arrow_up_icon())
        self.up_btn.setToolTip("Move provider up in fallback order")
        self.up_btn.clicked.connect(lambda: self.reorder_requested.emit(self, -1))
        self.down_btn = QToolButton()
        self.down_btn.setIcon(get_arrow_down_icon())
        self.down_btn.setToolTip("Move provider down in fallback order")
        self.down_btn.clicked.connect(lambda: self.reorder_requested.emit(self, 1))
        actions.addWidget(self.up_btn)
        actions.addWidget(self.down_btn)
        actions.addStretch()
        actions.addWidget(action("Remove Provider", self._confirm_provider))
        body.addWidget(self.provider_actions)
        self.provider_actions.hide()
        self.provider_confirmation = confirmation(
            f"Remove {provider.name}?", f"This removes the connection and its {len(provider.models)} saved models.",
            lambda: self.delete_requested.emit(self), self._cancel_provider_removal, "Remove Provider")
        body.addWidget(self.provider_confirmation)
        self.provider_confirmation.hide()
        self.details = QWidget()
        details = QVBoxLayout(self.details)
        details.setContentsMargins(0, 6, 0, 0)
        details.setSpacing(12)
        connection_actions = QHBoxLayout()
        self.connection_toggle = action("Connection settings  ▸", self._toggle_connection)
        self.connection_toggle.setObjectName("SettingsGhost")
        connection_actions.addWidget(self.connection_toggle)
        connection_actions.addStretch()
        self.connect_btn = action("Refresh models", self.refresh_catalog)
        self.connect_btn.setObjectName("SettingsGhost")
        connection_actions.addWidget(self.connect_btn)
        details.addLayout(connection_actions)
        self.connection_fields = QWidget()
        connection_body = QVBoxLayout(self.connection_fields)
        connection_body.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.name_input = QLineEdit(provider.name)
        self.name_input.textEdited.connect(self._rename)
        form.addRow("Connection name", self.name_input)
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
        connection_body.addLayout(form)
        self.proto_combo.currentIndexChanged.connect(self._connection_changed)
        self.base_url_input.textEdited.connect(self._connection_changed)
        self.key_input.textEdited.connect(self._connection_changed)
        self.connection_status = label("Not verified")
        connection_body.addWidget(self.connection_status)
        self.catalog_status = label("")
        connection_body.addWidget(self.catalog_status)
        details.addWidget(self.connection_fields)
        self.connection_fields.hide()
        models_header = QHBoxLayout()
        models_header.addWidget(label("My Models", "SettingsHeading"))
        models_header.addWidget(label("1 active" if provider.active_model else "No active model"))
        models_header.addStretch()
        self.add_model_btn = action("+ Add Model", self.add_model)
        models_header.addWidget(self.add_model_btn)
        details.addLayout(models_header)
        self.models_scroll = QScrollArea()
        self.models_scroll.setObjectName("ModelList")
        self.models_scroll.setWidgetResizable(True)
        self.models_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.models_scroll.setFixedHeight(214)
        self.models_container = QWidget()
        self.models_layout = QVBoxLayout(self.models_container)
        self.models_layout.setContentsMargins(6, 6, 6, 6)
        self.models_layout.setSpacing(2)
        self.models_scroll.setWidget(self.models_container)
        details.addWidget(self.models_scroll)
        self.test_result = label("")
        details.addWidget(self.test_result)
        body.addWidget(self.details)
        self.details.hide()
        self._render_models()

    def _enabled(self, value):
        self.provider.enabled = value
        self.changed.emit()

    def _rename(self, value):
        self.provider.name = value.strip()
        self.set_expanded(self._expanded)
        self.changed.emit()

    def _reveal(self):
        hidden = self.key_input.echoMode() == QLineEdit.EchoMode.Password
        self.key_input.setEchoMode(QLineEdit.EchoMode.Normal if hidden else QLineEdit.EchoMode.Password)
        self.reveal_btn.setText("Hide" if hidden else "Show")

    def set_expanded(self, expanded):
        self._expanded = expanded
        self.details.setVisible(expanded and self.provider_confirmation.isHidden())
        self.collapse_btn.setText(("▾  " if expanded else "▸  ") + self.provider.name)

    def _collapse(self):
        self.expansion_requested.emit(self)

    def _toggle_connection(self):
        expanded = self.connection_fields.isHidden()
        self.connection_fields.setVisible(expanded)
        self.connection_toggle.setText("Connection settings  ▾" if expanded else "Connection settings  ▸")

    def _confirm_provider(self):
        # Regenerate the description after additions or renaming in this draft.
        old = self.provider_confirmation
        index = self.layout().indexOf(old)
        self.layout().removeWidget(old)
        old.deleteLater()
        self.provider_confirmation = confirmation(
            f"Remove {self.provider.name}?",
            f"This removes the connection and its {len(self.provider.models)} saved models.",
            lambda: self.delete_requested.emit(self), self._cancel_provider_removal, "Remove Provider")
        self.layout().insertWidget(index, self.provider_confirmation)
        self.provider_actions.hide()
        self.details.hide()
        self.provider_confirmation.show()

    def _cancel_provider_removal(self):
        self.provider_confirmation.hide()
        self.set_expanded(self._expanded)

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
        self.connection_badge.setText("Reconnect")
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
            self.connection_badge.setText("Request failed")
            self.connection_status.setToolTip(error)
            self.test_result.setText(error)
            return
        if "catalog" in result:
            self.provider.catalog = result["catalog"]
            self.provider.catalog_updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self.connection_status.setText("Connected · Catalog loaded (models not individually tested)")
            self.connection_badge.setText("Connected")
            self._catalog_label()
            self._render_models()
        else:
            self.test_result.setText(result["test"])

    def add_model(self):
        self.editor_requested.emit(self, None)

    def _edit_model(self, profile):
        self.editor_requested.emit(self, profile)

    def save_model(self, profile):
        if any(m.id == profile.id for m in self.provider.models):
            self.provider.models = [profile if m.id == profile.id else m for m in self.provider.models]
        else:
            self.provider.models.append(profile)
        if not self.provider.active_model_id:
            self.provider.active_model_id = profile.id
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
        self._confirm_model_id = None
        self.models_scroll.setFixedHeight(214)
        self.provider.models = [m for m in self.provider.models if m.id != profile.id]
        if not self.provider.models:
            self.provider.active_model_id = ""
        self._render_models()
        self.changed.emit()

    def _activate(self, profile):
        self.provider.active_model_id = profile.id
        self._render_models()
        self.changed.emit()

    def _model_actions(self, profile):
        self._actions_model_id = None if self._actions_model_id == profile.id else profile.id
        self._confirm_model_id = None
        self.models_scroll.setFixedHeight(214)
        self._render_models()

    def _confirm_model(self, profile):
        self._confirm_model_id = profile.id
        self.models_scroll.setFixedHeight(258)
        self._actions_model_id = None
        self._render_models()

    def _cancel_model_removal(self):
        self._confirm_model_id = None
        self.models_scroll.setFixedHeight(214)
        self._render_models()

    def _render_models(self):
        position = self.models_scroll.verticalScrollBar().value()
        clear_layout(self.models_layout)
        if hasattr(self, "radio_group"):
            self.radio_group.deleteLater()
        self.radio_group = QButtonGroup(self)
        for profile in self.provider.models:
            active = profile.id == self.provider.active_model_id
            model_frame = QFrame()
            model_frame.setObjectName("ActiveModel" if active else "SavedModel")
            layout = QVBoxLayout(model_frame)
            layout.setContentsMargins(10, 8, 10, 8)
            layout.setSpacing(4)
            top = QHBoxLayout()
            radio = QRadioButton(profile.name)
            radio.setChecked(active)
            self.radio_group.addButton(radio)
            radio.clicked.connect(lambda checked, m=profile: self._activate(m))
            top.addWidget(radio, 1)
            if active:
                top.addWidget(label("Active", "SettingsPrimaryBadge"))
            more = action("···", lambda checked=False, m=profile: self._model_actions(m))
            more.setObjectName("SettingsGhost")
            top.addWidget(more)
            layout.addLayout(top)
            available = {item["id"] for item in self.provider.catalog}
            status = " · Not in latest catalog" if self.provider.catalog_updated_at and profile.model not in available else ""
            layout.addWidget(label(f"{profile.model} · {profile.reasoning or 'Provider defaults'}{status}"))
            if self._actions_model_id == profile.id:
                buttons = QHBoxLayout()
                buttons.addWidget(action("Test", lambda checked=False, m=profile: self.test_model(m)))
                buttons.addWidget(action("Settings", lambda checked=False, m=profile: self._edit_model(m)))
                buttons.addWidget(action("Duplicate", lambda checked=False, m=profile: self._duplicate(m)))
                buttons.addStretch()
                buttons.addWidget(action("Remove", lambda checked=False, m=profile: self._confirm_model(m)))
                layout.addLayout(buttons)
            if self._confirm_model_id == profile.id:
                blocked = active and len(self.provider.models) > 1
                description = ("Select another active model before removing this configuration." if blocked else
                               f"Your active model, {self.provider.active_model.name}, will stay selected." if self.provider.active_model and not active else
                               "This provider will have no saved model until you add one.")
                prompt = confirmation(f"Remove {profile.name}?", description,
                                      lambda checked=False, m=profile: self._remove_model(m),
                                      self._cancel_model_removal, "Remove Model")
                prompt.findChild(QPushButton, "SettingsDanger").setEnabled(not blocked)
                layout.addWidget(prompt)
            self.models_layout.addWidget(model_frame)
        self.models_layout.addStretch()
        self.summary.setText(f"{self.provider.active_model.name if self.provider.active_model else 'No model selected'} · {len(self.provider.models)} models")
        self._catalog_label()
        self.models_layout.activate()
        self.models_container.adjustSize()
        self.models_scroll.verticalScrollBar().setValue(position)

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
        outer.setContentsMargins(24, 24, 24, 24)
        self.pages = QStackedWidget()
        outer.addWidget(self.pages)
        self.overview = QWidget()
        self.pages.addWidget(self.overview)
        outer = QVBoxLayout(self.overview)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(14)
        header = QHBoxLayout()
        title = QLabel("Providers & Models")
        title.setObjectName("SettingsHeaderTitle")
        header.addWidget(title, 1)
        close = QToolButton()
        close.setIcon(get_exit_icon())
        close.setObjectName("SettingsCloseBtn")
        close.clicked.connect(self.closed.emit)
        header.addWidget(close)
        outer.addLayout(header)
        subtitle = label("Manage connections and choose one active model per provider.")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
        self.footer_status = label("Changes are saved after Apply.")
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
        self._close_editor()
        self.config = config
        self.selected_provider_id = config.selected_provider_id
        clear_layout(self.cards_layout)
        self.cards = []
        providers = copy.deepcopy(list(config.providers) if config.providers is not None else migrate_models(list(config.models)))
        for provider in providers:
            self._append(provider)
        self._rebuild()
        if self.cards:
            self.cards[0].set_expanded(True)
        self.footer_status.setText("Changes are saved after Apply.")

    def _append(self, provider):
        card = ProviderCard(provider, self.cards_container)
        card.changed.connect(self._refresh_priority_badges)
        card.reorder_requested.connect(self._reorder)
        card.delete_requested.connect(self._delete)
        card.expansion_requested.connect(self._expand)
        card.editor_requested.connect(self._open_editor)
        self.cards.append(card)
        return card

    def _handle_add_card(self):
        card = self._append(create_provider(self.preset_combo.currentData()))
        self._rebuild()
        self._expand(card)
        card._toggle_connection()
        self.scroll_area.ensureWidgetVisible(card)

    def _expand(self, target):
        expanded = not target._expanded
        for card in self.cards:
            card._cancel_provider_removal()
            card.set_expanded(card is target and expanded)

    def _open_editor(self, card, profile):
        self.editor = ModelEditor(card.provider, profile, self)
        self.editor.saved.connect(lambda result: (card.save_model(result), self._close_editor()))
        self.editor.cancelled.connect(self._close_editor)
        self.editor.close_requested.connect(self.closed.emit)
        self.pages.addWidget(self.editor)
        self.pages.setCurrentWidget(self.editor)

    def _close_editor(self):
        self.pages.setCurrentWidget(self.overview)
        editor = getattr(self, "editor", None)
        if editor is not None:
            self.pages.removeWidget(editor)
            editor.deleteLater()
            self.editor = None

    def back(self):
        if getattr(self, "editor", None):
            self.editor.back()
        else:
            self.closed.emit()

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
