"""Render the editor scene to an image; copy to clipboard or save to disk."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication, QGraphicsScene


def render_scene(scene: QGraphicsScene, source: QRectF, size: QSize) -> QImage:
    """Render ``source`` (scene units) into a ``size``-pixel image, without
    selection chrome. Pass the capture's physical size for native resolution."""
    # Hide selection rectangles / handles in the rendered output.
    selected = list(scene.selectedItems())
    for item in selected:
        item.setSelected(False)

    image = QImage(size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    # Ignore aspect: source and size describe the same capture, and keeping
    # aspect could shift the result a pixel through float rounding.
    scene.render(painter, target=QRectF(image.rect()), source=source,
                 aspectRatioMode=Qt.AspectRatioMode.IgnoreAspectRatio)
    painter.end()

    for item in selected:
        item.setSelected(True)
    return image


def copy_to_clipboard(image: QImage) -> None:
    QApplication.clipboard().setImage(image)


def save_to_downloads(image: QImage) -> Path:
    """Save the image to the user's Downloads folder. Returns the path."""
    downloads = Path.home() / "Downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = downloads / f"screenshot-{ts}.png"
    image.save(str(out), "PNG")
    return out
