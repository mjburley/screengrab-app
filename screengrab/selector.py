"""Full-screen drag-to-select overlay."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget


class SelectorOverlay(QWidget):
    """A frameless, top-most overlay that lets the user drag-select a region.

    Emits ``region_selected(QRect, QPixmap)`` when the user releases the mouse
    on a non-empty selection. The QRect is in *overlay-local* coordinates and
    the QPixmap is the cropped region of the captured desktop. Emits
    ``cancelled`` if the user presses Esc or releases on an empty selection.
    """

    region_selected = Signal(QRect, QPixmap)
    cancelled = Signal()

    def __init__(self, desktop_pixmap: QPixmap, desktop_rect: QRect) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        # Tool windows on Windows often skip keyboard focus; force it so Esc works.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._pixmap = desktop_pixmap
        self._desktop_rect = desktop_rect
        self.setGeometry(desktop_rect)

        self._origin: QPoint | None = None
        self._current: QPoint | None = None

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().showEvent(event)
        self.activateWindow()
        self.raise_()
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        # Capture all keyboard input regardless of focus state — belt and braces.
        self.grabKeyboard()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.releaseKeyboard()
        super().closeEvent(event)

    # ----- selection geometry -----
    def _selection_rect(self) -> QRect:
        if self._origin is None or self._current is None:
            return QRect()
        return QRect(self._origin, self._current).normalized()

    # ----- painting -----
    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        p = QPainter(self)
        p.drawPixmap(0, 0, self._pixmap)

        # Dim the whole screen
        dim = QColor(0, 0, 0, 110)
        p.fillRect(self.rect(), dim)

        sel = self._selection_rect()
        if not sel.isNull() and sel.width() > 0 and sel.height() > 0:
            # Re-draw the selected region at full brightness
            p.drawPixmap(sel, self._pixmap, sel)

            # Border
            pen = QPen(QColor(255, 255, 255), 1)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(sel)

            # Size caption near the cursor
            caption = f"{sel.width()} × {sel.height()}"
            font = QFont("Segoe UI", 10)
            p.setFont(font)
            metrics = p.fontMetrics()
            tw = metrics.horizontalAdvance(caption) + 12
            th = metrics.height() + 6
            cx = min(sel.right() + 8, self.width() - tw - 4)
            cy = max(sel.bottom() + 8, 4)
            if cy + th > self.height():
                cy = sel.top() - th - 8
            cap_rect = QRect(cx, cy, tw, th)
            p.fillRect(cap_rect, QBrush(QColor(0, 0, 0, 180)))
            p.setPen(QColor(255, 255, 255))
            p.drawText(cap_rect, Qt.AlignmentFlag.AlignCenter, caption)

        p.end()

    # ----- mouse -----
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.position().toPoint()
            self._current = self._origin
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self._cancel()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._origin is not None:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        sel = self._selection_rect()
        if sel.width() < 4 or sel.height() < 4:
            self._cancel()
            return
        sel = sel.intersected(self.rect())
        cropped = self._pixmap.copy(sel)
        self.region_selected.emit(sel, cropped)
        self.close()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
        else:
            super().keyPressEvent(event)

    def _cancel(self) -> None:
        self.cancelled.emit()
        self.close()
