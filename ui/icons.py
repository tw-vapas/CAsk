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


def get_gear_icon(color: str = "#cdd6f4", size: int = 16) -> QIcon:
    """Return settings gear icon."""
    svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='{size}' height='{size}' viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
  <circle cx='12' cy='12' r='3'></circle>
  <path d='M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z'></path>
</svg>"""
    return _svg_to_icon(svg, size)


def get_arrow_up_icon(color: str = "#cdd6f4", size: int = 14) -> QIcon:
    """Return crisp up arrow icon."""
    svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='{size}' height='{size}' viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'>
  <polyline points='18 15 12 9 6 15'></polyline>
</svg>"""
    return _svg_to_icon(svg, size)


def get_arrow_down_icon(color: str = "#cdd6f4", size: int = 14) -> QIcon:
    """Return crisp down arrow icon."""
    svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='{size}' height='{size}' viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'>
  <polyline points='6 9 12 15 18 9'></polyline>
</svg>"""
    return _svg_to_icon(svg, size)


def get_eye_icon(visible: bool = False, color: str = "#cdd6f4", size: int = 14) -> QIcon:
    """Return password eye toggle icon."""
    if visible:
        svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='{size}' height='{size}' viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
  <path d='M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z'></path>
  <circle cx='12' cy='12' r='3'></circle>
</svg>"""
    else:
        svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='{size}' height='{size}' viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
  <path d='M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24'></path>
  <line x1='1' y1='1' x2='23' y2='23'></line>
</svg>"""
    return _svg_to_icon(svg, size)


def get_test_icon(color: str = "#f9e2af", size: int = 14) -> QIcon:
    """Return test connection lightning icon."""
    svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='{size}' height='{size}' viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
  <polygon points='13 2 3 14 12 14 11 22 21 10 12 10 13 2'></polygon>
</svg>"""
    return _svg_to_icon(svg, size)
