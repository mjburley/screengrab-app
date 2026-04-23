"""Render the editor scene to an image; copy to clipboard or save to disk."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication, QGraphicsScene


def render_scene(scene: QGraphicsScene, source: QRectF) -> QImage:
    """Render the scene at native resolution, ignoring selection chrome."""
    # Hide selection rectangles / handles in the rendered output.
    selected = list(scene.selectedItems())
    for item in selected:
        item.setSelected(False)

    image = QImage(int(source.width()), int(source.height()), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    scene.render(painter, target=QRectF(image.rect()), source=source)
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
