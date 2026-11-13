"""Draggable / editable annotation items used by the editor scene."""
from __future__ import annotations

import math

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsSceneHoverEvent,
    QGraphicsSceneMouseEvent,
    QGraphicsTextItem,
    QStyleOptionGraphicsItem,
    QWidget,
)

from .tools import DEFAULT_TEXT_SIZE

HANDLE_SIZE = 8.0
STROKE_WIDTH = 3


# ---------------------------------------------------------------------------
# Rectangle
# ---------------------------------------------------------------------------

# 8 resize handle positions on a rectangle's bounding box.
_HANDLES = ("tl", "t", "tr", "r", "br", "b", "bl", "l")
_HANDLE_CURSORS = {
    "tl": Qt.CursorShape.SizeFDiagCursor,
    "br": Qt.CursorShape.SizeFDiagCursor,
    "tr": Qt.CursorShape.SizeBDiagCursor,
    "bl": Qt.CursorShape.SizeBDiagCursor,
    "t": Qt.CursorShape.SizeVerCursor,
    "b": Qt.CursorShape.SizeVerCursor,
    "l": Qt.CursorShape.SizeHorCursor,
    "r": Qt.CursorShape.SizeHorCursor,
}


class MovableRectItem(QGraphicsRectItem):
    """A coloured-stroke rectangle that the user can drag and resize."""

    def __init__(self, rect: QRectF, color: QColor) -> None:
        super().__init__(rect)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.set_color(color)
        self._active_handle: str | None = None
        self._press_rect: QRectF = QRectF()
        self._press_pos: QPointF = QPointF()

    # public API used by editor when palette changes
    def set_color(self, color: QColor) -> None:
        pen = QPen(color, STROKE_WIDTH)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        self.setPen(pen)
        self.setBrush(Qt.BrushStyle.NoBrush)

    def color(self) -> QColor:
        return self.pen().color()

    # ---- handle geometry ----
    def _handle_rect(self, name: str) -> QRectF:
        r = self.rect()
        s = HANDLE_SIZE
        cx = {"l": r.left(), "r": r.right(), "t": r.left(), "b": r.left()}
        # compute centre per handle name
        if name == "tl":
            cx_, cy_ = r.left(), r.top()
        elif name == "tr":
            cx_, cy_ = r.right(), r.top()
        elif name == "bl":
            cx_, cy_ = r.left(), r.bottom()
        elif name == "br":
            cx_, cy_ = r.right(), r.bottom()
        elif name == "t":
            cx_, cy_ = r.center().x(), r.top()
        elif name == "b":
            cx_, cy_ = r.center().x(), r.bottom()
        elif name == "l":
            cx_, cy_ = r.left(), r.center().y()
        elif name == "r":
            cx_, cy_ = r.right(), r.center().y()
        else:
            return QRectF()
        return QRectF(cx_ - s / 2, cy_ - s / 2, s, s)

    def _handle_at(self, pos: QPointF) -> str | None:
        for name in _HANDLES:
            if self._handle_rect(name).contains(pos):
                return name
        return None

    # paint includes selection handles
    def boundingRect(self) -> QRectF:  # noqa: N802
        # Enlarge slightly so handles aren't clipped.
        return super().boundingRect().adjusted(-HANDLE_SIZE, -HANDLE_SIZE, HANDLE_SIZE, HANDLE_SIZE)

    def paint(  # noqa: D401 - Qt API
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(self.pen())
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect())

        if self.isSelected():
            painter.setPen(QPen(QColor(0, 120, 215), 1))
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            for name in _HANDLES:
                painter.drawRect(self._handle_rect(name))

    # ---- mouse handling for resize ----
    def hoverMoveEvent(self, event: QGraphicsSceneHoverEvent) -> None:  # noqa: N802
        if self.isSelected():
            handle = self._handle_at(event.pos())
            if handle:
                self.setCursor(QCursor(_HANDLE_CURSORS[handle]))
                return
        self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.isSelected():
            handle = self._handle_at(event.pos())
            if handle:
                self._active_handle = handle
                self._press_rect = QRectF(self.rect())
                self._press_pos = event.pos()
                event.accept()
                return
        self._active_handle = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if self._active_handle is not None:
            self.prepareGeometryChange()
            r = QRectF(self._press_rect)
            d = event.pos() - self._press_pos
            h = self._active_handle
            if "l" in h:
                r.setLeft(r.left() + d.x())
            if "r" in h:
                r.setRight(r.right() + d.x())
            if "t" in h:
                r.setTop(r.top() + d.y())
            if "b" in h:
                r.setBottom(r.bottom() + d.y())
            self.setRect(r.normalized())
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        self._active_handle = None
        super().mouseReleaseEvent(event)


# ---------------------------------------------------------------------------
# Arrow
# ---------------------------------------------------------------------------

ARROW_HEAD_LEN = 16.0
ARROW_HEAD_WIDTH = 12.0


class ArrowItem(QGraphicsItem):
    """Line + filled triangle head; both endpoints drag-editable when selected."""

    def __init__(self, start: QPointF, end: QPointF, color: QColor) -> None:
        super().__init__()
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self._start = QPointF(start)
        self._end = QPointF(end)
        self._color = QColor(color)
        self._dragging: str | None = None  # 'start' or 'end'

    # API
    def set_color(self, color: QColor) -> None:
        self._color = QColor(color)
        self.update()

    def color(self) -> QColor:
        return QColor(self._color)

    def set_endpoints(self, start: QPointF, end: QPointF) -> None:
        self.prepareGeometryChange()
        self._start = QPointF(start)
        self._end = QPointF(end)

    # geometry
    def _line(self) -> QLineF:
        return QLineF(self._start, self._end)

    def boundingRect(self) -> QRectF:  # noqa: N802
        pad = max(STROKE_WIDTH, ARROW_HEAD_WIDTH) + HANDLE_SIZE
        return QRectF(self._start, self._end).normalized().adjusted(-pad, -pad, pad, pad)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        line = self._line()
        # Build a thick line region for hit testing
        pen = QPen(Qt.GlobalColor.black, max(STROKE_WIDTH * 2, 8))
        stroker = QPainterPath()
        stroker.moveTo(line.p1())
        stroker.lineTo(line.p2())
        from PySide6.QtGui import QPainterPathStroker

        s = QPainterPathStroker()
        s.setWidth(pen.widthF())
        path.addPath(s.createStroke(stroker))
        path.addPolygon(self._head_polygon())
        return path

    def _head_polygon(self) -> QPolygonF:
        line = self._line()
        if line.length() == 0:
            return QPolygonF()
        angle = math.atan2(line.dy(), line.dx())
        tip = self._end
        left = QPointF(
            tip.x() - ARROW_HEAD_LEN * math.cos(angle) + ARROW_HEAD_WIDTH / 2 * math.sin(angle),
            tip.y() - ARROW_HEAD_LEN * math.sin(angle) - ARROW_HEAD_WIDTH / 2 * math.cos(angle),
        )
        right = QPointF(
            tip.x() - ARROW_HEAD_LEN * math.cos(angle) - ARROW_HEAD_WIDTH / 2 * math.sin(angle),
            tip.y() - ARROW_HEAD_LEN * math.sin(angle) + ARROW_HEAD_WIDTH / 2 * math.cos(angle),
        )
        return QPolygonF([tip, left, right])

    def _handle_rect(self, which: str) -> QRectF:
        p = self._start if which == "start" else self._end
        s = HANDLE_SIZE
        return QRectF(p.x() - s / 2, p.y() - s / 2, s, s)

    def paint(  # noqa: D401
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        line = self._line()

        # Shorten the shaft so it ends at the base of the arrowhead.
        if line.length() > ARROW_HEAD_LEN:
            shaft = QLineF(line)
            shaft.setLength(line.length() - ARROW_HEAD_LEN * 0.8)
        else:
            shaft = line

        pen = QPen(self._color, STROKE_WIDTH)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(shaft)

        painter.setBrush(QBrush(self._color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(self._head_polygon())

        if self.isSelected():
            painter.setPen(QPen(QColor(0, 120, 215), 1))
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            painter.drawRect(self._handle_rect("start"))
            painter.drawRect(self._handle_rect("end"))

    # mouse
    def hoverMoveEvent(self, event: QGraphicsSceneHoverEvent) -> None:  # noqa: N802
        if self.isSelected() and (
            self._handle_rect("start").contains(event.pos())
            or self._handle_rect("end").contains(event.pos())
        ):
            self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.isSelected():
            if self._handle_rect("start").contains(event.pos()):
                self._dragging = "start"
                event.accept()
                return
            if self._handle_rect("end").contains(event.pos()):
                self._dragging = "end"
                event.accept()
                return
        self._dragging = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if self._dragging is not None:
            self.prepareGeometryChange()
            if self._dragging == "start":
                self._start = event.pos()
            else:
                self._end = event.pos()
            self.update()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        self._dragging = None
        super().mouseReleaseEvent(event)


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------


class TextItem(QGraphicsTextItem):
    """Editable text annotation. Single click selects/drags, double-click edits."""

    DEFAULT_TEXT = "Text"

    def __init__(
        self, color: QColor, text: str = "", size: int = DEFAULT_TEXT_SIZE
    ) -> None:
        super().__init__(text or self.DEFAULT_TEXT)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFont(QFont("Segoe UI", size))
        self.set_color(color)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

    def set_color(self, color: QColor) -> None:
        self.setDefaultTextColor(color)

    def set_font_size(self, size: int) -> None:
        font = self.font()
        font.setPointSize(size)
        self.setFont(font)

    def color(self) -> QColor:
        return self.defaultTextColor()

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        # Select all so the user can immediately overwrite the placeholder.
        cursor = self.textCursor()
        cursor.select(cursor.SelectionType.Document)
        self.setTextCursor(cursor)
        super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event) -> None:  # noqa: N802
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        # If user erased everything, drop the item from the scene.
        if not self.toPlainText().strip() and self.scene() is not None:
            self.scene().removeItem(self)
            return
        super().focusOutEvent(event)
