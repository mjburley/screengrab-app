"""Screen capture using mss → QPixmap."""
from __future__ import annotations

import mss
from PySide6.QtCore import QRect
from PySide6.QtGui import QImage, QPixmap


def grab_virtual_screen() -> tuple[QPixmap, QRect]:
    """Grab the entire virtual desktop (union of all monitors).

    Returns the pixmap and the QRect describing its position in virtual-screen
    coordinates (top-left may be negative if a monitor is left of the primary).
    """
    with mss.mss() as sct:
        mon = sct.monitors[0]  # index 0 = bounding rect of all monitors
        raw = sct.grab(mon)
        # mss gives BGRA; QImage.Format_ARGB32 expects ARGB on little-endian, but
        # Format_RGB32 with BGRA bytes renders correctly on Windows.
        image = QImage(raw.bgra, raw.width, raw.height, QImage.Format.Format_RGB32).copy()

    pixmap = QPixmap.fromImage(image)
    rect = QRect(mon["left"], mon["top"], mon["width"], mon["height"])
    return pixmap, rect
