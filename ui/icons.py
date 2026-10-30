"""SVG vector icons for CAsk HUD controls."""

from __future__ import annotations

from typing import Optional

try:
    from PyQt6.QtCore import QByteArray
    from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
    from PyQt6.QtSvg import QSvgRenderer
except ImportError:
    pass


def _svg_to_icon(svg_str: str, size: int = 16) -> QIcon:
    """Render an SVG string into a transparent QIcon."""
    try:
        renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
        if not renderer.isValid():
            return QIcon()
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)
    except Exception:
        return QIcon()


def get_search_icon(color: str = "#e6ebf5", size: int = 16) -> QIcon:
    """Return crisp magnifying glass icon."""
    svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='{size}' height='{size}' viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'>
  <circle cx='11' cy='11' r='7'></circle>
  <line x1='21' y1='21' x2='16' y2='16'></line>
</svg>"""
    return _svg_to_icon(svg, size)


def get_copy_icon(color: str = "#e6ebf5", size: int = 16) -> QIcon:
    """Return crisp clipboard copy icon."""
    svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='{size}' height='{size}' viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
  <rect x='8' y='8' width='13' height='13' rx='2'></rect>
  <path d='M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2'></path>
</svg>"""
    return _svg_to_icon(svg, size)


def get_pin_icon(pinned: bool = False, size: int = 16) -> QIcon:
    """Return pushpin icon with highlight fill when pinned."""
    stroke = "#f9e2af" if pinned else "#e6ebf5"
    fill = "#f9e2af" if pinned else "none"
    svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='{size}' height='{size}' viewBox='0 0 24 24' fill='{fill}' stroke='{stroke}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
  <line x1='12' y1='17' x2='12' y2='22'></line>
  <path d='M5 17h14l-2-5V5h1V3H6v2h1v7l-2 5z'></path>
</svg>"""
    return _svg_to_icon(svg, size)


def get_exit_icon(color: str = "#e6ebf5", size: int = 16) -> QIcon:
    """Return crisp close / exit cross icon."""
    svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='{size}' height='{size}' viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'>
  <line x1='18' y1='6' x2='6' y2='18'></line>
  <line x1='6' y1='6' x2='18' y2='18'></line>
</svg>"""
    return _svg_to_icon(svg, size)


def get_grip_icon(color: str = "#a6adc8", size: int = 16) -> QIcon:
    """Return drag grip / reorder handle icon (6 dots)."""
    svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='{size}' height='{size}' viewBox='0 0 24 24' fill='{color}'>
  <circle cx='9' cy='6' r='1.5'></circle>
  <circle cx='15' cy='6' r='1.5'></circle>
  <circle cx='9' cy='12' r='1.5'></circle>
  <circle cx='15' cy='12' r='1.5'></circle>
  <circle cx='9' cy='18' r='1.5'></circle>
  <circle cx='15' cy='18' r='1.5'></circle>
</svg>"""
    return _svg_to_icon(svg, size)
