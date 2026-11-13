"""Render provider-first CAsk UI mockups using placeholder data only.

Run: QT_QPA_PLATFORM=offscreen python3 resources/references/generate-provider-mockups.py
These views do not load credentials, contact providers, or modify application settings.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QRadioButton, QVBoxLayout, QWidget,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ui.icons import get_gear_icon


STYLE = """
QWidget { color: #e6ebf5; background: transparent; font-size: 13px; }
QFrame#Panel { background: #1b1f26; border: 1px solid #454b56; border-radius: 14px; }
QFrame#Card { background: #262d38; border: 1px solid #454b56; border-radius: 10px; }
QFrame#Selected { background: #313640; border: 1px solid #bca779; border-radius: 8px; }
QFrame#Row { background: #202630; border: 1px solid #3a424f; border-radius: 8px; }
QLabel#Title { font-size: 21px; font-weight: bold; color: #f9e2af; }
QLabel#Heading { font-size: 15px; font-weight: bold; }
QLabel#Muted { color: #bbc4d6; font-size: 12px; }
QLabel#Badge { color: #a6e3a1; background: #334840; border-radius: 5px; padding: 5px 9px; }
QLabel#PrimaryBadge { color: #f9e2af; background: #484336; border-radius: 5px; padding: 5px 9px; }
QLineEdit, QComboBox { background: #171b23; border: 1px solid #454b56;
    border-radius: 6px; padding: 8px 10px; min-height: 18px; }
QComboBox QAbstractItemView { background: #202630; selection-background-color: #484336; }
QPushButton { background: #303743; border: 1px solid #505968; border-radius: 6px;
    padding: 8px 12px; min-height: 16px; }
QPushButton#Primary { background: #f9e2af; color: #171b23; border: none; font-weight: bold; }
QPushButton#Quiet { background: transparent; border: none; color: #bbc4d6; }
QRadioButton { spacing: 12px; }
QRadioButton::indicator { width: 17px; height: 17px; border: 1px solid #8c96a8; border-radius: 9px; }
QRadioButton::indicator:checked { background: #f9e2af; border: 1px solid #f9e2af; border-radius: 9px; }
"""


def label(text, role=None):
    widget = QLabel(text)
    if role:
        widget.setObjectName(role)
    return widget


def button(text, primary=False, quiet=False):
    widget = QPushButton(text)
    if primary or quiet:
        widget.setObjectName("Primary" if primary else "Quiet")
    return widget


def row(*widgets):
    layout = QHBoxLayout()
    layout.setSpacing(10)
    for widget in widgets:
        if widget is None:
            layout.addStretch()
        else:
            layout.addWidget(widget)
    return layout


def frame(role, margin=18, spacing=14):
    widget = QFrame()
    widget.setObjectName(role)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(margin, margin, margin, margin)
    layout.setSpacing(spacing)
    return widget, layout


def combo(items):
    widget = QComboBox()
    widget.addItems(items)
    return widget


def entry(text):
    widget = QLineEdit(text)
    widget.setReadOnly(True)
    return widget


def model_row(name, effort, active, group):
    widget, layout = frame("Selected" if active else "Row", 14, 8)
    radio = QRadioButton(name)
    radio.setChecked(active)
    group.addButton(radio)
    layout.addLayout(row(radio, None, label("Active" if active else "Saved", "PrimaryBadge" if active else "Muted")))
    layout.addWidget(label(f"gpt-6.1-sol  /  Reasoning: {effort}", "Muted"))
    layout.addLayout(row(button("Test"), button("Settings"), button("Duplicate"), None, button("Remove", quiet=True)))
    return widget


def provider_settings():
    panel, layout = frame("Panel", 24, 18)
    layout.addLayout(row(label("Providers & Models", "Title"), None, button("Close", quiet=True)))
    layout.addWidget(label("Connect once. Save your models. Choose one active model per provider.", "Muted"))
    card, body = frame("Card", 18, 14)
    body.addLayout(row(label("OpenAI Personal", "Heading"), label("Primary", "PrimaryBadge"), None, label("Connected", "Badge"), button("Collapse", quiet=True)))
    body.addLayout(row(label("OpenAI  /  API Key", "Muted"), None, button("Edit connection", quiet=True)))
    body.addWidget(entry("https://api.openai.com/v1"))
    body.addLayout(row(label("API key is saved", "Muted"), None, button("Refresh models")))
    body.addLayout(row(label("My Models", "Heading"), None, label("2 saved · 1 active", "Muted")))
    group = QButtonGroup(panel)
    body.addWidget(model_row("Sol Medium", "Medium", True, group))
    body.addWidget(model_row("Sol High", "High", False, group))
    body.addLayout(row(button("+ Add Model"), None, label("Active: Sol Medium", "Muted")))
    layout.addWidget(card)
    fallback, body = frame("Card", 18, 10)
    body.addLayout(row(label("Groq Cloud", "Heading"), label("Fallback 1", "Muted"), None, label("Connected", "Badge"), button("Expand", quiet=True)))
    body.addWidget(label("Active model: GPT OSS 120B  ·  1 saved model", "Muted"))
    layout.addWidget(fallback)
    layout.addLayout(row(button("+ Add Provider"), None, label("Provider order: OpenAI → Groq", "Muted")))
    layout.addStretch()
    layout.addLayout(row(label("Changes take effect after Apply.", "Muted"), None, button("Cancel"), button("Apply", primary=True)))
    return panel


def model_picker():
    panel, layout = frame("Panel", 24, 16)
    layout.addLayout(row(label("Add Model", "Title"), None, button("Close", quiet=True)))
    layout.addLayout(row(label("OpenAI Personal", "Heading"), None, label("Catalog loaded", "Badge")))
    search = QLineEdit()
    search.setPlaceholderText("Search models by name or ID...")
    layout.addWidget(search)
    layout.addLayout(row(label("Available models", "Muted"), None, button("Refresh models", quiet=True)))
    group = QButtonGroup(panel)
    for name, model_id, selected in (
        ("GPT-6.1 Sol", "gpt-6.1-sol", True),
        ("GPT-6.1 Terra", "gpt-6.1-terra", False),
        ("GPT-6 Luna", "gpt-6-luna", False),
    ):
        widget, body = frame("Selected" if selected else "Row", 14, 6)
        radio = QRadioButton(name)
        radio.setChecked(selected)
        group.addButton(radio)
        body.addWidget(radio)
        body.addWidget(label(model_id, "Muted"))
        layout.addWidget(widget)
    layout.addLayout(row(label("Display name", "Muted"), None, label("Reasoning effort", "Muted")))
    layout.addLayout(row(entry("Sol Medium"), combo(["Medium", "Low", "High", "XHigh", "Max"])))
    layout.addLayout(row(button("Enter model ID manually", quiet=True), None))
    layout.addStretch()
    layout.addLayout(row(label("Save a model configuration to this provider.", "Muted"), None, button("Cancel"), button("Add Model", primary=True)))
    return panel


def quick_switch():
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    input_panel, input_layout = frame("Panel", 20, 0)
    query = QLineEdit()
    query.setPlaceholderText("Type what's on your mind...")
    ask = button("", primary=True)
    arrow = QPixmap(20, 20)
    arrow.fill(Qt.GlobalColor.transparent)
    painter = QPainter(arrow)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#171b23"), 2, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.drawLine(4, 10, 16, 10)
    painter.drawLine(11, 5, 16, 10)
    painter.drawLine(11, 15, 16, 10)
    painter.end()
    ask.setIcon(QIcon(arrow))
    ask.setIconSize(QSize(20, 20))
    ask.setFixedWidth(40)
    ask.setAccessibleName("Ask")
    ask.setToolTip("Send question")
    input_layout.addLayout(row(query, ask))
    layout.addWidget(input_panel)
    settings = button("")
    settings.setIcon(get_gear_icon(size=20))
    settings.setIconSize(QSize(20, 20))
    settings.setFixedWidth(40)
    settings.setAccessibleName("Settings")
    settings.setToolTip("Provider and model settings")
    controls = row(
        button("Provider: OpenAI Personal ▾"),
        button("Model: Sol Medium ▾"), None, settings,
    )
    controls.setContentsMargins(20, 0, 20, 0)
    layout.addLayout(controls)
    return panel


def render(app, panel, width, height, filename):
    host = QWidget()
    host.setWindowFlags(Qt.WindowType.FramelessWindowHint)
    host.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(panel)
    host.resize(width, height)
    host.show()
    app.processEvents()
    image = host.grab().toImage()
    for x, y in ((0, 0), (image.width()-1, 0), (0, image.height()-1), (image.width()-1, image.height()-1)):
        assert image.pixelColor(x, y).alpha() == 0
    if filename == "provider-quick-switch-mockup.png":
        input_panel = panel.findChild(QFrame, "Panel")
        scale = image.devicePixelRatio()
        gap_y = round((input_panel.geometry().bottom() + 6) * scale)
        assert image.pixelColor(image.width() // 2, gap_y).alpha() == 0
        assert image.pixelColor(image.width() * 3 // 4, image.height() - 15).alpha() == 0
    destination = Path(__file__).resolve().parent / filename
    assert image.save(str(destination))
    print(f"{destination.name}: {image.width()}x{image.height()}, transparent corners verified")
    host.close()


if __name__ == "__main__":
    app = QApplication([])
    app.setFont(QFont("DejaVu Sans", 10))
    app.setStyleSheet(STYLE)
    render(app, provider_settings(), 860, 870, "provider-settings-mockup.png")
    render(app, model_picker(), 760, 650, "provider-model-picker-mockup.png")
    render(app, quick_switch(), 860, 150, "provider-quick-switch-mockup.png")
