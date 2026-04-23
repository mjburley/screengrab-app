"""Screen capture using mss → QPixmap, with high-DPI awareness."""
from __future__ import annotations

import mss
from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication, QImage, QPixmap


def grab_virtual_screen() -> tuple[QPixmap, QRect, float]:
    """Grab the entire virtual desktop (union of all monitors).

    Returns:
        pixmap: full-resolution screenshot, tagged with ``devicePixelRatio`` so
            Qt renders it at logical-unit size while preserving native pixels.
        logical_rect: virtual-desktop bounds in Qt's device-independent units —
            use this for sizing overlay windows.
        dpr: the device pixel ratio applied to the pixmap (1.0 on a non-scaled
            display; e.g. 1.5 at Windows 150% scaling, 2.0 at 200%).
    """
    with mss.mss() as sct:
        mon = sct.monitors[0]  # bounding rect of all monitors, in physical pixels
        raw = sct.grab(mon)
        image = QImage(
            raw.bgra, raw.width, raw.height, QImage.Format.Format_RGB32
        ).copy()

    pixmap = QPixmap.fromImage(image)

    primary = QGuiApplication.primaryScreen()
    dpr = primary.devicePixelRatio() if primary is not None else 1.0
    pixmap.setDevicePixelRatio(dpr)

    # Qt's virtual-desktop geometry is already in logical (device-independent)
    # units, which is what we want for overlay window sizing/placement.
    if primary is not None:
        logical_rect = primary.virtualGeometry()
    else:
        logical_rect = QRect(mon["left"], mon["top"], mon["width"], mon["height"])

    return pixmap, logical_rect, dpr
