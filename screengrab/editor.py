"""Annotation editor window."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QGuiApplication,
    QIcon,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QToolBar,
    QWidget,
)

from . import export
from .items import ArrowItem, MovableRectItem, TextItem
from .tools import PALETTE, ToolMode

TOOLBAR_HEIGHT = 44
SWATCH_SIZE = 22


class EditorScene(QGraphicsScene):
    """Scene that owns the screenshot pixmap and forwards drawing-tool clicks."""

    request_create = Signal(QPointF, QPointF)  # raw start/current pos forwarded to view

    def __init__(self, pixmap: QPixmap) -> None:
        super().__init__()
        self.bg_item = QGraphicsPixmapItem(pixmap)
        self.bg_item.setZValue(-1000)
        self.bg_item.setFlag(self.bg_item.GraphicsItemFlag.ItemIsSelectable, False)
        self.addItem(self.bg_item)
        self.setSceneRect(QRectF(pixmap.rect()))


class EditorView(QGraphicsView):
    """View that handles tool-driven creation of new items."""

    def __init__(self, scene: EditorScene, window: "EditorWindow") -> None:
        super().__init__(scene)
        self._window = window
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)

        self._creating: MovableRectItem | ArrowItem | None = None
        self._press_scene_pos: QPointF | None = None

    # ---- mouse: tool-driven creation ----
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        tool = self._window.active_tool
        if event.button() == Qt.MouseButton.LeftButton and tool != ToolMode.SELECT:
            scene_pos = self.mapToScene(event.position().toPoint())
            self._press_scene_pos = scene_pos
            color = self._window.active_color
            scene = self.scene()
            if tool == ToolMode.RECT:
                item = MovableRectItem(QRectF(scene_pos, scene_pos), color)
                scene.addItem(item)
                self._creating = item
            elif tool == ToolMode.ARROW:
                item = ArrowItem(scene_pos, scene_pos, color)
                scene.addItem(item)
                self._creating = item
            elif tool == ToolMode.TEXT:
                item = TextItem(color)
                # Anchor near the click; keep movable from there.
                item.setPos(scene_pos)
                scene.addItem(item)
                scene.clearSelection()
                item.setSelected(True)
                # Enter edit mode immediately
                item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
                item.setFocus(Qt.FocusReason.MouseFocusReason)
                cursor = item.textCursor()
                cursor.select(cursor.SelectionType.Document)
                item.setTextCursor(cursor)
                self._window.set_tool(ToolMode.SELECT)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._creating is not None and self._press_scene_pos is not None:
            scene_pos = self.mapToScene(event.position().toPoint())
            if isinstance(self._creating, MovableRectItem):
                self._creating.setRect(QRectF(self._press_scene_pos, scene_pos).normalized())
            elif isinstance(self._creating, ArrowItem):
                self._creating.set_endpoints(self._press_scene_pos, scene_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._creating is not None:
            # If the user just clicked without dragging, drop tiny items.
            scene = self.scene()
            if isinstance(self._creating, MovableRectItem):
                if self._creating.rect().width() < 4 or self._creating.rect().height() < 4:
                    scene.removeItem(self._creating)
                else:
                    scene.clearSelection()
                    self._creating.setSelected(True)
            elif isinstance(self._creating, ArrowItem):
                line_len = (
                    (self._creating._end.x() - self._creating._start.x()) ** 2
                    + (self._creating._end.y() - self._creating._start.y()) ** 2
                ) ** 0.5
                if line_len < 6:
                    scene.removeItem(self._creating)
                else:
                    scene.clearSelection()
                    self._creating.setSelected(True)
            self._creating = None
            self._press_scene_pos = None
            self._window.set_tool(ToolMode.SELECT)
            event.accept()
            return
        super().mouseReleaseEvent(event)


def _swatch_icon(color: QColor, selected: bool) -> QIcon:
    pm = QPixmap(SWATCH_SIZE, SWATCH_SIZE)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(color)
    if selected:
        from PySide6.QtGui import QPen

        p.setPen(QPen(QColor(0, 0, 0), 2))
    else:
        from PySide6.QtGui import QPen

        p.setPen(QPen(QColor(120, 120, 120), 1))
    p.drawEllipse(2, 2, SWATCH_SIZE - 4, SWATCH_SIZE - 4)
    p.end()
    return QIcon(pm)


class EditorWindow(QMainWindow):
    """Main annotation window."""

    def __init__(self, screenshot: QPixmap) -> None:
        super().__init__()
        self.setWindowTitle("ScreenGrab")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)

        self.active_tool: ToolMode = ToolMode.SELECT
        self.active_color: QColor = QColor(PALETTE[0][1])

        self.scene = EditorScene(screenshot)
        self.view = EditorView(self.scene, self)
        self.setCentralWidget(self.view)

        self._build_toolbar()
        self._build_shortcuts()
        self._size_to_screenshot(screenshot.size())

    # ---- layout ----
    def _build_toolbar(self) -> None:
        tb = QToolBar()
        tb.setMovable(False)
        tb.setIconSize(QSize(SWATCH_SIZE, SWATCH_SIZE))
        tb.setStyleSheet(
            "QToolBar { background:#f5f5f5; border-bottom:1px solid #ddd; padding:4px; spacing:6px; }"
            "QPushButton { padding:6px 12px; border:1px solid #ccc; border-radius:4px;"
            "  background:white; }"
            "QPushButton:checked { background:#e6f0ff; border-color:#3b82f6; }"
            "QPushButton:hover { background:#eee; }"
        )
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        # Tool buttons
        self.btn_rect = QPushButton("▭ Rectangle")
        self.btn_arrow = QPushButton("→ Arrow")
        self.btn_text = QPushButton("T Text")
        for btn, mode in (
            (self.btn_rect, ToolMode.RECT),
            (self.btn_arrow, ToolMode.ARROW),
            (self.btn_text, ToolMode.TEXT),
        ):
            btn.setCheckable(True)
            btn.clicked.connect(lambda _checked=False, m=mode: self.set_tool(m))
            tb.addWidget(btn)

        tb.addSeparator()

        # Colour swatches
        self._swatch_buttons: list[QPushButton] = []
        swatch_holder = QWidget()
        sh_layout = QHBoxLayout(swatch_holder)
        sh_layout.setContentsMargins(4, 0, 4, 0)
        sh_layout.setSpacing(4)
        for name, color in PALETTE:
            b = QPushButton()
            b.setToolTip(name)
            b.setFixedSize(SWATCH_SIZE + 8, SWATCH_SIZE + 8)
            b.setIcon(_swatch_icon(color, color == self.active_color))
            b.setIconSize(QSize(SWATCH_SIZE, SWATCH_SIZE))
            b.setStyleSheet("QPushButton { padding:2px; border:none; background:transparent; }")
            b.clicked.connect(lambda _checked=False, c=color: self._on_swatch(c))
            sh_layout.addWidget(b)
            self._swatch_buttons.append(b)
        tb.addWidget(swatch_holder)

        # Spacer
        from PySide6.QtWidgets import QSizePolicy

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        # Action buttons
        self.btn_copy = QPushButton("Copy")
        self.btn_save = QPushButton("Save")
        self.btn_copy.clicked.connect(self._on_copy)
        self.btn_save.clicked.connect(self._on_save)
        tb.addWidget(self.btn_copy)
        tb.addWidget(self.btn_save)

    def _build_shortcuts(self) -> None:
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, activated=self._delete_selected)
        QShortcut(QKeySequence(Qt.Key.Key_Backspace), self, activated=self._delete_selected)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self.close)
        QShortcut(QKeySequence("Ctrl+C"), self, activated=self._on_copy)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._on_save)

    def _size_to_screenshot(self, size) -> None:
        screen = QGuiApplication.primaryScreen().availableGeometry()
        max_w = int(screen.width() * 0.9)
        max_h = int(screen.height() * 0.9) - TOOLBAR_HEIGHT
        target_w = min(size.width(), max_w) + 40
        target_h = min(size.height(), max_h) + TOOLBAR_HEIGHT + 40
        self.resize(target_w, target_h)
        # Centre on the primary screen
        x = screen.x() + (screen.width() - target_w) // 2
        y = screen.y() + (screen.height() - target_h) // 2
        self.move(max(x, screen.x()), max(y, screen.y()))

    # ---- tool / colour state ----
    def set_tool(self, tool: ToolMode) -> None:
        self.active_tool = tool
        self.btn_rect.setChecked(tool == ToolMode.RECT)
        self.btn_arrow.setChecked(tool == ToolMode.ARROW)
        self.btn_text.setChecked(tool == ToolMode.TEXT)
        if tool == ToolMode.SELECT:
            self.view.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        else:
            self.view.viewport().setCursor(Qt.CursorShape.CrossCursor)
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)

    def _on_swatch(self, color: QColor) -> None:
        self.active_color = QColor(color)
        # Refresh swatch icons (border highlights selected)
        for btn, (_name, c) in zip(self._swatch_buttons, PALETTE):
            btn.setIcon(_swatch_icon(c, c == self.active_color))
        # Recolour selected items
        for item in self.scene.selectedItems():
            if hasattr(item, "set_color"):
                item.set_color(self.active_color)

    # ---- delete / export ----
    def _delete_selected(self) -> None:
        for item in self.scene.selectedItems():
            if item is self.scene.bg_item:
                continue
            self.scene.removeItem(item)

    def _scene_source_rect(self) -> QRectF:
        return QRectF(self.scene.bg_item.pixmap().rect())

    def _on_copy(self) -> None:
        image = export.render_scene(self.scene, self._scene_source_rect())
        export.copy_to_clipboard(image)
        self.statusBar().showMessage("Copied to clipboard", 1500)

    def _on_save(self) -> None:
        image = export.render_scene(self.scene, self._scene_source_rect())
        path = export.save_to_downloads(image)
        self.statusBar().showMessage(f"Saved {path.name} to Downloads", 2500)
