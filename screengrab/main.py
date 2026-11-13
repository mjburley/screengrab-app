"""ScreenGrab entry point — wires tray, hotkey listener, and capture flow."""
from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

# Tell Windows we are per-monitor DPI aware *before* QApplication is created.
# Without this, PyInstaller-built .exes default to system-DPI awareness and Qt
# sees the wrong DPI on high-resolution monitors (4K/scaled displays look broken).
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except (AttributeError, OSError):
        pass  # Older Windows versions or already set — best effort.

# Honour fractional scaling factors (e.g. 150%) without rounding artefacts.
QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
    Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
)

from .capture import grab_virtual_screen  # noqa: E402 — must follow DPI setup
from .editor import EditorWindow  # noqa: E402
from .hotkey import HotkeyListener  # noqa: E402
from .selector import SelectorOverlay  # noqa: E402
from .tray import Tray  # noqa: E402


class ScreenGrabApp:
    # After hiding open editors, wait this long before grabbing the screen so
    # Windows has actually removed them from the desktop image. Measured on
    # Win11: a hidden window was already absent from an mss grab at 0ms; 100ms
    # is headroom for slower machines.
    HIDE_DELAY_MS = 100
    # Each extra open editor is offset by this much so they don't stack exactly.
    CASCADE_STEP = QPoint(30, 30)

    def __init__(self, qapp: QApplication) -> None:
        self.qapp = qapp
        self.qapp.setQuitOnLastWindowClosed(False)

        self.tray = Tray()
        self.hotkey = HotkeyListener()

        self._overlay: SelectorOverlay | None = None
        # Any number of editors can be open; a new capture can start while
        # they are. Only one capture (hide → grab → overlay) runs at a time.
        self._editors: list[EditorWindow] = []
        self._hidden: list[EditorWindow] = []
        self._busy = False

        self.tray.capture_requested.connect(self.start_capture)
        self.tray.quit_requested.connect(self.quit)
        self.hotkey.triggered.connect(self.start_capture)

    def run(self) -> int:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(
                None,
                "ScreenGrab",
                "System tray is not available on this system.",
            )
            return 1
        self.tray.show()
        self.hotkey.start()
        self.tray.notify("ScreenGrab", "Running. Press PrintScreen to capture.")
        return self.qapp.exec()

    def quit(self) -> None:
        self.hotkey.stop()
        if self._overlay is not None:
            self._overlay.close()
        for editor in list(self._editors):
            editor.close()
        self.qapp.quit()

    # ---- capture flow ----
    def start_capture(self) -> None:
        if self._busy:
            return
        self._busy = True
        # Hide open editors so they don't appear in the new screenshot (as the
        # Snipping Tool does); they come back when the overlay finishes.
        self._hidden = [e for e in self._editors if e.isVisible()]
        for editor in self._hidden:
            editor.hide()
        if self._hidden:
            QTimer.singleShot(self.HIDE_DELAY_MS, self._grab)
        else:
            self._grab()

    def _grab(self) -> None:
        try:
            pixmap, rect, dpr = grab_virtual_screen()
            self._overlay = SelectorOverlay(pixmap, rect, dpr)
            self._overlay.region_selected.connect(self._on_region_selected)
            self._overlay.cancelled.connect(self._restore_editors)
            self._overlay.destroyed.connect(self._on_overlay_destroyed)
            self._overlay.show()
            self._overlay.raise_()
            self._overlay.activateWindow()
        except Exception as exc:  # pragma: no cover - defensive
            self._restore_editors()
            self._busy = False
            QMessageBox.critical(None, "ScreenGrab", f"Capture failed:\n{exc}")

    def _restore_editors(self) -> None:
        for editor in self._hidden:
            editor.show()
        self._hidden = []

    def _on_region_selected(self, _rect: QRect, cropped: QPixmap) -> None:
        # Restore the old editors first so the new one opens on top of them.
        self._restore_editors()
        self._open_editor(cropped)

    def _on_overlay_destroyed(self) -> None:
        # The only place _busy clears after a successful grab: the overlay
        # always closes (select, Esc, right-click, tiny drag) and is
        # WA_DeleteOnClose, so this always fires.
        self._overlay = None
        self._restore_editors()  # normally already done; safety net
        self._busy = False

    def _open_editor(self, cropped: QPixmap) -> None:
        editor = EditorWindow(cropped)
        editor.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        editor.destroyed.connect(lambda _obj=None, e=editor: self._forget_editor(e))
        offset = len(self._editors) % 8
        if offset:
            editor.move(editor.pos() + self.CASCADE_STEP * offset)
        self._editors.append(editor)
        editor.show()
        editor.raise_()
        editor.activateWindow()

    def _forget_editor(self, editor: EditorWindow) -> None:
        self._editors = [e for e in self._editors if e is not editor]
        self._hidden = [e for e in self._hidden if e is not editor]


def main() -> int:
    qapp = QApplication(sys.argv)
    qapp.setApplicationName("ScreenGrab")
    app = ScreenGrabApp(qapp)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
