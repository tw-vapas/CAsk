"""Render or preview single-window Settings proposals without accessing user data.

Render: python3 resources/references/generate-settings-v2-mockups.py
Preview: python3 resources/references/generate-settings-v2-mockups.py --preview
"""

import argparse
import os
import sys
from pathlib import Path

if "--preview" not in sys.argv:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QRadioButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)


STYLE = """
QWidget { background: transparent; color: #e6ebf5; font-size: 10pt;
    font-family: "JetBrainsMono Nerd Font", "JetBrains Mono", monospace; }
#Surface { background: rgba(27,31,38,0.75); border: 1px solid rgba(255,255,255,0.16);
    border-top: 1px solid rgba(255,255,255,0.32); border-radius: 14px; }
#Provider { background: rgba(38,45,56,0.70); border: 1px solid rgba(255,255,255,0.12); border-radius: 10px; }
#ModelList { background: rgba(17,17,27,0.22); border: 1px solid rgba(255,255,255,0.10); border-radius: 8px; }
#Selected { background: rgba(249,226,175,0.10); border: none; border-radius: 6px; }
#Confirm { background: rgba(243,139,168,0.08); border: 1px solid rgba(243,139,168,0.32); border-radius: 8px; }
QLabel#Title { color: #f9e2af; font-size: 14pt; font-weight: 700; }
QLabel#ProviderName, QPushButton#ProviderName { font-size: 11pt; font-weight: 600; }
QLabel#Heading { font-size: 10pt; font-weight: 600; }
QLabel#Description { font-size: 9pt; color: #bbc4d6; }
QLabel#Badge { font-size: 9pt; color: #a6e3a1; }
QLabel#PrimaryBadge { font-size: 9pt; color: #f9e2af; }
QPushButton { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.15);
    border-radius: 6px; padding: 7px 12px; }
QPushButton:hover { background: rgba(249,226,175,0.18); }
QPushButton#Ghost, QPushButton#ProviderName { background: transparent; border: none; padding: 4px 6px; }
QPushButton#Primary { background: #f9e2af; color: #11111b; border: none; font-weight: 600; }
QPushButton#Danger { background: rgba(243,139,168,0.15); color: #f3a9bb; border-color: rgba(243,139,168,0.45); }
QLineEdit, QComboBox { background: rgba(17,17,27,0.65); border: 1px solid rgba(255,255,255,0.12);
    border-radius: 6px; padding: 9px 10px; }
QComboBox QAbstractItemView { background: #1b1f26; selection-background-color: #484336; }
QRadioButton { spacing: 10px; }
QRadioButton::indicator { width: 16px; height: 16px; border: 1px solid #a6adc8; border-radius: 8px; }
QRadioButton::indicator:checked { background: #f9e2af; border-color: #f9e2af; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { width: 5px; background: transparent; margin: 4px 0; }
QScrollBar::handle:vertical { background: rgba(187,196,214,0.35); border-radius: 2px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""


def text(value, role=None):
    widget = QLabel(value)
    widget.setWordWrap(False)
    if role:
        widget.setObjectName(role)
    return widget


def button(value, callback=None, role=None):
    widget = QPushButton(value)
    if role:
        widget.setObjectName(role)
    if callback:
        widget.clicked.connect(callback)
    return widget


def row(*items):
    layout = QHBoxLayout()
    layout.setSpacing(10)
    for item in items:
        if item is None:
            layout.addStretch()
        else:
            layout.addWidget(item)
    return layout


def surface(role=None, margin=0, spacing=12):
    widget = QFrame()
    if role:
        widget.setObjectName(role)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(margin, margin, margin, margin)
    layout.setSpacing(spacing)
    return widget, layout


def field(layout, label, value, options=None):
    layout.addWidget(text(label, "Description"))
    widget = QComboBox() if options else QLineEdit(value)
    if options:
        widget.addItems(options)
        widget.setCurrentText(value)
    layout.addWidget(widget)
    return widget


class SettingsPreview(QWidget):
    """One top-level window with stacked pages, accordions, and inline confirmation."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CAsk Settings UI Proposal")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        panel, layout = surface("Surface", 24, 0)
        outer.addWidget(panel)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages)
        self.open_provider = "OpenAI Personal"
        self.confirm = None
        self.actions_for = None
        self.active_model = "Sol Medium"
        self.selected_model = "GPT-6.1 Sol"
        self.models = ["Sol Medium", "Sol High", "Sol Low", "Sol Review"]
        self.removed_providers = set()
        self.home = self.make_home()
        self.picker = self.make_picker()
        self.configure = self.make_configuration(False)
        self.editor = self.make_configuration(True)
        for page in (self.home, self.picker, self.configure, self.editor):
            self.pages.addWidget(page)
        self.resize(800, 760)

    def title(self, layout, title, subtitle, back=None):
        line = QHBoxLayout()
        if back:
            line.addWidget(button("← Back", back, "Ghost"))
        line.addWidget(text(title, "Title"), 1)
        line.addWidget(button("×", self.close, "Ghost"))
        layout.addLayout(line)
        layout.addWidget(text(subtitle, "Description"))

    def navigate(self, target):
        self.pages.setCurrentWidget(target)

    def make_home(self):
        page, layout = surface(spacing=14)
        self.title(layout, "Providers & Models", "Manage connections and choose one active model per provider.")
        self.provider_scroll = QScrollArea()
        self.provider_scroll.setWidgetResizable(True)
        self.provider_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.providers = QWidget()
        self.provider_layout = QVBoxLayout(self.providers)
        self.provider_layout.setContentsMargins(0, 0, 0, 0)
        self.provider_layout.setSpacing(12)
        self.provider_scroll.setWidget(self.providers)
        layout.addWidget(self.provider_scroll, 1)
        layout.addLayout(row(button("+ Add Provider", self.show_connection), None))
        layout.addLayout(row(text("Changes are saved after Apply.", "Description"), None,
                             button("Cancel", self.close), button("Apply", self.show_applied, "Primary")))
        self.render_providers()
        return page

    def render_providers(self):
        while self.provider_layout.count():
            item = self.provider_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.deleteLater()
        for name, detail in (("OpenAI Personal", "Sol Medium · 4 models"),
                             ("Groq Cloud", "GPT OSS 120B · 1 model")):
            if name in self.removed_providers:
                continue
            expanded = name == self.open_provider
            card, body = surface("Provider", 16, 12)
            header = button(("▾  " if expanded else "▸  ") + name,
                            lambda checked=False, n=name: self.toggle_provider(n), "ProviderName")
            body.addLayout(row(header, None, text("Primary" if name == "OpenAI Personal" else "", "PrimaryBadge"),
                               text("Connected" if name != "Ollama Local" else "Not connected", "Badge"),
                               button("···", lambda checked=False: self.confirm_provider(), "Ghost")))
            body.addWidget(text(detail, "Description"))
            if expanded:
                if name != "OpenAI Personal":
                    body.addWidget(text("My Models", "Heading"))
                    model = QRadioButton("GPT OSS 120B")
                    model.setChecked(True)
                    body.addWidget(model)
                    body.addWidget(text("openai/gpt-oss-120b", "Description"))
                elif self.confirm == "provider":
                    body.addWidget(self.confirmation("Remove OpenAI Personal?", "This removes the connection and its 4 saved models.", self.remove_provider, "Remove Provider"))
                else:
                    body.addLayout(row(button("Connection settings  ▸", self.show_connection, "Ghost"), None,
                                       button("Refresh models", self.show_refreshed, "Ghost")))
                    body.addLayout(row(text("My Models", "Heading"), text("1 active", "Description"), None,
                                       button("+ Add Model", lambda: self.navigate(self.picker))))
                    body.addWidget(self.make_model_list())
            self.provider_layout.addWidget(card)
        self.provider_layout.addStretch()

    def toggle_provider(self, name):
        self.open_provider = None if self.open_provider == name else name
        self.confirm = None
        self.render_providers()

    def make_model_list(self):
        container, body = surface("ModelList", 6, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(246 if self.confirm == "model" else 202)
        container.setFixedHeight(scroll.height() + 12)
        content, rows = surface(spacing=2)
        group = QButtonGroup(content)
        for index, name in enumerate(self.models):
            item, item_layout = surface("Selected" if name == self.active_model else None, 10, 4)
            radio = QRadioButton(name)
            radio.setChecked(name == self.active_model)
            group.addButton(radio)
            radio.clicked.connect(lambda checked=False, n=name: self.activate(n))
            item_layout.addLayout(row(radio, None, text("Active" if name == self.active_model else "", "PrimaryBadge"),
                                      button("···", lambda checked=False, n=name: self.show_model_actions(n), "Ghost")))
            effort = {"Sol Medium": "Medium", "Sol High": "High", "Sol Low": "Low", "Sol Review": "XHigh"}.get(name, "Medium")
            item_layout.addWidget(text(f"gpt-6.1-sol · {effort}", "Description"))
            if self.confirm == "model" and name == "Sol High":
                item_layout.addWidget(self.confirmation("Remove Sol High?", "Your active model, Sol Medium, will stay selected.", self.remove_model, "Remove Model"))
            elif self.actions_for == name:
                item_layout.addLayout(row(button("Edit", lambda: self.navigate(self.editor)), button("Test", self.show_test),
                                          button("Duplicate", self.duplicate), None,
                                          button("Remove", self.confirm_model, "Danger")))
            rows.addWidget(item)
        rows.addStretch()
        scroll.setWidget(content)
        body.addWidget(scroll)
        self.model_scroll = scroll
        return container

    def confirmation(self, title, message, remove, caption):
        panel, layout = surface("Confirm", 12, 8)
        layout.addWidget(text(title, "Heading"))
        layout.addWidget(text(message, "Description"))
        cancel = button("Cancel", self.cancel_confirmation)
        cancel.setDefault(True)
        layout.addLayout(row(None, cancel, button(caption, remove, "Danger")))
        return panel

    def cancel_confirmation(self):
        self.confirm = None
        self.render_providers()

    def confirm_model(self):
        self.actions_for = None
        self.confirm = "model"
        self.render_providers()

    def confirm_provider(self):
        self.open_provider = "OpenAI Personal"
        self.confirm = "provider"
        self.render_providers()

    def show_model_actions(self, name):
        self.actions_for = None if self.actions_for == name else name
        self.render_providers()

    def activate(self, name):
        self.active_model = name
        self.render_providers()

    def remove_model(self):
        if "Sol High" in self.models:
            self.models.remove("Sol High")
        self.cancel_confirmation()

    def remove_provider(self):
        self.removed_providers.add("OpenAI Personal")
        self.confirm = None
        self.open_provider = "Groq Cloud"
        self.render_providers()

    def make_picker(self):
        page, layout = surface(spacing=14)
        self.title(layout, "Add Model", "OpenAI Personal · Step 1 of 2 — Choose a model", lambda: self.navigate(self.home))
        search = QLineEdit()
        search.setPlaceholderText("Search available models...")
        layout.addWidget(search)
        layout.addLayout(row(text("Provider catalog", "Heading"), None, text("3 models · Updated just now", "Description")))
        group = QButtonGroup(page)
        items = []
        for title, model_id in (("GPT-6.1 Sol", "gpt-6.1-sol"), ("GPT-6.1 Terra", "gpt-6.1-terra"), ("GPT-6 Luna", "gpt-6-luna")):
            item, body = surface("Selected" if title == "GPT-6.1 Sol" else None, 14, 7)
            radio = QRadioButton(title)
            radio.setChecked(title == "GPT-6.1 Sol")
            group.addButton(radio)
            body.addWidget(radio)
            body.addWidget(text(model_id, "Description"))
            layout.addWidget(item)
            items.append((item, title, model_id))
        search.textChanged.connect(lambda value: [item.setVisible(value.lower() in (title + model_id).lower()) for item, title, model_id in items])
        layout.addLayout(row(button("Enter model ID manually", lambda: self.navigate(self.configure), "Ghost"), None))
        layout.addStretch()
        layout.addLayout(row(None, button("Cancel", lambda: self.navigate(self.home)),
                             button("Continue →", lambda: self.navigate(self.configure), "Primary")))
        return page

    def make_configuration(self, editing):
        page, layout = surface(spacing=14)
        self.title(layout, "Edit Model" if editing else "Configure Model",
                   "OpenAI Personal · Sol High" if editing else "OpenAI Personal · Step 2 of 2 — Configure model",
                   lambda: self.navigate(self.home if editing else self.picker))
        identity, body = surface("ModelList", 14, 6)
        body.addWidget(text("GPT-6.1 Sol", "Heading"))
        body.addWidget(text("gpt-6.1-sol", "Description"))
        layout.addWidget(identity)
        field(layout, "Display name", "Sol High" if editing else "Sol Medium")
        field(layout, "Reasoning effort", "High" if editing else "Medium", ["Low", "Medium", "High", "XHigh", "Max"])
        layout.addWidget(text("Choose how much reasoning this model uses.", "Description"))
        advanced, advanced_layout = surface(spacing=12)
        field(advanced_layout, "Output limit", "Provider default")
        advanced_layout.addWidget(text("Temperature is not available for this reasoning model.", "Description"))
        toggle = button("▸ Advanced", role="Ghost")
        advanced.hide()
        toggle.clicked.connect(lambda: (advanced.setVisible(not advanced.isVisible()), toggle.setText("▾ Advanced" if advanced.isVisible() else "▸ Advanced")))
        layout.addLayout(row(toggle, None))
        layout.addWidget(advanced)
        layout.addStretch()
        layout.addWidget(text("Return here at any time. Changes are saved after Apply on the provider page.", "Description"))
        layout.addLayout(row(None, button("Cancel", lambda: self.navigate(self.home)),
                             button("Save Model" if editing else "Add Model", lambda: self.navigate(self.home), "Primary")))
        return page

    def show_connection(self):
        self.setWindowTitle("CAsk Settings UI Proposal — Connection settings preview")

    def show_refreshed(self):
        self.setWindowTitle("CAsk Settings UI Proposal — Catalog refresh preview")

    def show_applied(self):
        self.setWindowTitle("CAsk Settings UI Proposal — Apply preview; no settings saved")

    def show_test(self):
        self.setWindowTitle("CAsk Settings UI Proposal — Test preview; no API request sent")

    def duplicate(self):
        self.models.append("Sol Copy")
        self.render_providers()


def capture(app, window, filename):
    for _ in range(3):
        app.sendPostedEvents()
        app.processEvents()
    assert sum(widget.isVisible() for widget in app.topLevelWidgets()) == 1
    if filename == "settings-v2-overview.png":
        assert window.model_scroll.verticalScrollBar().maximum() > 0
    image = window.grab().toImage()
    for x, y in ((0, 0), (image.width()-1, 0), (0, image.height()-1), (image.width()-1, image.height()-1)):
        assert image.pixelColor(x, y).alpha() == 0
    assert 190 <= image.pixelColor(image.width() // 2, 8).alpha() <= 192
    path = Path(__file__).resolve().parent / filename
    assert image.save(str(path))
    print(f"{path.name}: {image.width()}x{image.height()}, alpha verified")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    app = QApplication([])
    app.setFont(QFont("DejaVu Sans", 10))
    app.setStyleSheet(STYLE)
    window = SettingsPreview()
    window.show()
    if args.preview:
        raise SystemExit(app.exec())
    capture(app, window, "settings-v2-overview.png")
    for page, filename in ((window.picker, "settings-v2-add-model.png"),
                           (window.configure, "settings-v2-configure-model.png"),
                           (window.editor, "settings-v2-edit-model.png")):
        window.navigate(page)
        capture(app, window, filename)
    window.navigate(window.home)
    window.confirm_model()
    capture(app, window, "settings-v2-remove-model.png")
    window.confirm_provider()
    capture(app, window, "settings-v2-remove-provider.png")
    window.close()
