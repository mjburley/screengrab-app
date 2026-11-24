"""Annotation editor window."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QGuiApplication,
    QIcon,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QComboBox,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QToolBar,
    QWidget,
)

from . import export, ocr
from .items import ArrowItem, MovableRectItem, TextItem
from .tools import DEFAULT_TEXT_SIZE, PALETTE, TEXT_SIZES, ToolMode

TOOLBAR_HEIGHT = 44
SWATCH_SIZE = 22
OCR_HINT = "Drag over the text you want to copy, or click once for the whole screenshot"
OCR_BAND_COLOR = QColor(37, 99, 235)

# The toolbar is drawn by a stylesheet, which overrides the native palette, so
# every colour — text included — must be set for both Windows colour schemes.
# Leaving text to the palette gave white-on-white buttons in dark mode.
THEMES: dict[str, dict[str, str]] = {
    "light": {
        "bar": "#f5f5f5", "bar_border": "#ddd", "btn": "white", "btn_border": "#ccc",
        "text": "#1a1a1a", "hover": "#eee", "checked": "#e6f0ff", "accent": "#3b82f6",
        "swatch_ring": "#000000",
    },
    "dark": {
        "bar": "#2b2b2b", "bar_border": "#3d3d3d", "btn": "#3a3a3a", "btn_border": "#555",
        "text": "#f2f2f2", "hover": "#474747", "checked": "#1e3a5f", "accent": "#3b82f6",
        "swatch_ring": "#ffffff",
    },
}
TOOLBAR_QSS = (
    "QToolBar {{ background:{bar}; border-bottom:1px solid {bar_border}; padding:4px; spacing:6px; }}"
    "QPushButton {{ padding:6px 12px; border:1px solid {btn_border}; border-radius:4px;"
    "  background:{btn}; color:{text}; }}"
    "QPushButton:checked {{ background:{checked}; border-color:{accent}; }}"
    "QPushButton:hover {{ background:{hover}; }}"
    # No QComboBox rule: the native combo follows the palette, which matches
    # the scheme chosen here. Partly styling it leaves a stray native border
    # around its drop-down arrow.
)


def _current_theme() -> dict[str, str]:
    dark = QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    return THEMES["dark" if dark else "light"]


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
        # Temporary rubber band for the Extract Text tool — removed on release,
        # never part of the exported image.
        self._ocr_band: QGraphicsRectItem | None = None
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
                item = TextItem(color, size=self._window.active_text_size)
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
            elif tool == ToolMode.OCR:
                band = QGraphicsRectItem(QRectF(scene_pos, scene_pos))
                pen = QPen(OCR_BAND_COLOR, 1, Qt.PenStyle.DashLine)
                pen.setCosmetic(True)
                band.setPen(pen)
                band.setBrush(QBrush(QColor(OCR_BAND_COLOR.red(), OCR_BAND_COLOR.green(),
                                            OCR_BAND_COLOR.blue(), 40)))
                band.setZValue(10_000)
                scene.addItem(band)
                self._ocr_band = band
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._ocr_band is not None and self._press_scene_pos is not None:
            scene_pos = self.mapToScene(event.position().toPoint())
            self._ocr_band.setRect(QRectF(self._press_scene_pos, scene_pos).normalized())
            event.accept()
            return
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
        if self._ocr_band is not None:
            region: QRectF | None = self._ocr_band.rect()
            self.scene().removeItem(self._ocr_band)
            self._ocr_band = None
            self._press_scene_pos = None
            self._window.set_tool(ToolMode.SELECT)
            # A click without a drag means "the whole screenshot".
            if region.width() < 4 or region.height() < 4:
                region = None
            self._window.extract_text(region)
            event.accept()
            return
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


def _swatch_icon(color: QColor, selected: bool, ring: QColor) -> QIcon:
    pm = QPixmap(SWATCH_SIZE, SWATCH_SIZE)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(color)
    if selected:
        p.setPen(QPen(ring, 2))
    else:
        p.setPen(QPen(QColor(120, 120, 120), 1))
    p.drawEllipse(2, 2, SWATCH_SIZE - 4, SWATCH_SIZE - 4)
    p.end()
    return QIcon(pm)


class EditorWindow(QMainWindow):
    """Main annotation window."""

    # Last text size the user picked. Class-level so it carries over to the next
    # capture while the tray app keeps running (deliberately not persisted —
    # the app writes nothing to disk/registry beyond the autostart Run key).
    _remembered_text_size: int = DEFAULT_TEXT_SIZE

    def __init__(self, screenshot: QPixmap) -> None:
        super().__init__()
        self.setWindowTitle("ScreenGrab")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)

        self.active_tool: ToolMode = ToolMode.SELECT
        self.active_color: QColor = QColor(PALETTE[0][1])
        self.active_text_size: int = EditorWindow._remembered_text_size

        self.scene = EditorScene(screenshot)
        self.view = EditorView(self.scene, self)
        self.setCentralWidget(self.view)

        self._build_toolbar()
        self._apply_theme()
        # Re-theme open editors when Windows switches light/dark. The connection
        # drops automatically when this window is deleted.
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._apply_theme)
        self._build_shortcuts()
        self._size_to_screenshot(screenshot.size())

    # ---- layout ----
    def _build_toolbar(self) -> None:
        tb = QToolBar()
        self.toolbar = tb
        tb.setMovable(False)
        tb.setIconSize(QSize(SWATCH_SIZE, SWATCH_SIZE))
        # Stylesheet and swatch icons are set by _apply_theme().
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

        # Text size — applies to new text and to any selected text items.
        self.size_combo = QComboBox()
        self.size_combo.setToolTip("Text size")
        # NoFocus so picking a size doesn't end an in-progress text edit.
        self.size_combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        for size in TEXT_SIZES:
            self.size_combo.addItem(str(size), size)
        self.size_combo.setCurrentIndex(TEXT_SIZES.index(self.active_text_size))
        # `activated` (not currentIndexChanged) so re-picking the shown size
        # still applies it to a newly selected item.
        self.size_combo.activated.connect(self._on_text_size)
        tb.addWidget(self.size_combo)

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
        self.btn_ocr = QPushButton("Extract Text")
        self.btn_ocr.setCheckable(True)
        self.btn_ocr.setToolTip(
            "Drag over text to copy it to the clipboard, or click once for the "
            "whole screenshot.\nCtrl+Shift+C copies all the text straight away."
        )
        self.btn_ocr.clicked.connect(lambda _checked=False: self.set_tool(ToolMode.OCR))
        tb.addWidget(self.btn_ocr)

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
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, activated=self.extract_text)

    def _size_to_screenshot(self, size) -> None:
        screen = QGuiApplication.primaryScreen().availableGeometry()
        max_w = int(screen.width() * 0.9)
        max_h = int(screen.height() * 0.9) - TOOLBAR_HEIGHT
        # Toolbar dictates the floor — without this, narrow screenshots clip Copy/Save.
        min_w = self.toolbar.sizeHint().width() + 16
        self.setMinimumWidth(min_w)
        target_w = max(min(size.width(), max_w) + 40, min_w)
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
        self.btn_ocr.setChecked(tool == ToolMode.OCR)
        if tool == ToolMode.OCR:
            self.statusBar().showMessage(OCR_HINT)
        elif self.statusBar().currentMessage() == OCR_HINT:
            self.statusBar().clearMessage()
        if tool == ToolMode.SELECT:
            self.view.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        else:
            self.view.viewport().setCursor(Qt.CursorShape.CrossCursor)
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)

    def _apply_theme(self, *_args) -> None:
        theme = _current_theme()
        self._swatch_ring = QColor(theme["swatch_ring"])
        self.toolbar.setStyleSheet(TOOLBAR_QSS.format(**theme))
        self._refresh_swatches()

    def _refresh_swatches(self) -> None:
        # The ring around the active colour uses the theme's text colour.
        for btn, (_name, c) in zip(self._swatch_buttons, PALETTE):
            btn.setIcon(_swatch_icon(c, c == self.active_color, self._swatch_ring))

    def _on_swatch(self, color: QColor) -> None:
        self.active_color = QColor(color)
        self._refresh_swatches()
        # Recolour selected items
        for item in self.scene.selectedItems():
            if hasattr(item, "set_color"):
                item.set_color(self.active_color)

    def _on_text_size(self, index: int) -> None:
        size = self.size_combo.itemData(index)
        self.active_text_size = size
        EditorWindow._remembered_text_size = size
        for item in self.scene.selectedItems():
            if isinstance(item, TextItem):
                item.set_font_size(size)

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

    def extract_text(self, region: QRectF | None = None) -> None:
        """OCR ``region`` of the screenshot (scene coords = screenshot pixels),
        or all of it when ``region`` is None, and copy the text."""
        # OCR the original capture, not the annotated render — drawn boxes and
        # text annotations would only add noise.
        pixmap = self.scene.bg_item.pixmap()
        where = "the screenshot"
        if region is not None:
            where = "the selection"
            crop = region.toAlignedRect().intersected(pixmap.rect())
            if crop.isEmpty():
                # Dragged entirely outside the image. Must not reach copy():
                # QPixmap.copy() with an empty rect copies the *whole* pixmap.
                self.statusBar().showMessage(f"No text found in {where}", 2500)
                return
            pixmap = pixmap.copy(crop)
        image = pixmap.toImage()
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            text = ocr.extract_text(image)
            error = None
        except ocr.OcrError as exc:
            text, error = "", exc
        finally:
            QGuiApplication.restoreOverrideCursor()

        if error is not None:
            QMessageBox.warning(self, "ScreenGrab", str(error))
            return
        if not text.strip():
            self.statusBar().showMessage(f"No text found in {where}", 2500)
            return
        QGuiApplication.clipboard().setText(text)
        lines = len(text.splitlines())
        self.statusBar().showMessage(
            f"Copied {lines} line{'s' if lines != 1 else ''} of text to clipboard", 2500
        )
