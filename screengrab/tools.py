"""Tool/colour state for the editor."""
from __future__ import annotations

from enum import Enum, auto

from PySide6.QtGui import QColor


class ToolMode(Enum):
    SELECT = auto()
    RECT = auto()
    ARROW = auto()
    TEXT = auto()
    OCR = auto()  # drag a region to extract its text (not an annotation)


# Order matters — first entry is the default active colour.
PALETTE: list[tuple[str, QColor]] = [
    ("Red", QColor(220, 38, 38)),
    ("Black", QColor(0, 0, 0)),
    ("White", QColor(255, 255, 255)),
    ("Yellow", QColor(250, 204, 21)),
    ("Green", QColor(34, 197, 94)),
    ("Blue", QColor(37, 99, 235)),
]

# Point sizes offered for text annotations.
TEXT_SIZES: list[int] = [12, 14, 18, 24, 32, 48, 72]
DEFAULT_TEXT_SIZE = 14
