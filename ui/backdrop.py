"""Rounded logical-pixel regions shared by input masking and native blur."""
from math import ceil, sqrt

from PyQt6.QtCore import QRect
from PyQt6.QtGui import QRegion


def rounded_rectangles(rect: QRect, radius: int):
    """Return conservative scanlines, excluding every transparent rounded corner.

    Coordinates are surface-local logical pixels. Wayland applies output scaling;
    multiplying these by devicePixelRatio would blur outside the painted surface.
    Adjacent identical scanlines are merged to keep protocol traffic small.
    """
    if rect.isEmpty():
        return []
    radius = min(radius, rect.width() / 2, rect.height() / 2)
    rectangles = []
    for row in range(rect.height()):
        edge = min(row + 0.5, rect.height() - row - 0.5)
        inset = ceil(radius - sqrt(max(0, radius * radius - (radius - edge) ** 2))) if edge < radius else 0
        width = rect.width() - 2 * inset
        if width <= 0:
            continue
        x, y = rect.x() + inset, rect.y() + row
        if rectangles and rectangles[-1][0] == x and rectangles[-1][2] == width and rectangles[-1][1] + rectangles[-1][3] == y:
            previous = rectangles[-1]
            rectangles[-1] = (x, previous[1], width, previous[3] + 1)
        else:
            rectangles.append((x, y, width, 1))
    return rectangles


def as_region(rectangles):
    region = QRegion()
    for rectangle in rectangles:
        region |= QRegion(QRect(*rectangle))
    return region
