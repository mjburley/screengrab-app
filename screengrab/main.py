"""ScreenGrab entry point — wires tray, hotkey listener, and capture flow."""
from __future__ import annotations

import sys

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from .capture import grab_virtual_screen
from .editor import EditorWindow
from .hotkey import HotkeyListener
from .selector import SelectorOverlay
from .tray import Tray


class ScreenGrabApp:
    def __init__(self, qapp: QApplication) -> None:
        self.qapp = qapp
        self.qapp.setQuitOnLastWindowClosed(False)

        self.tray = Tray()
        self.hotkey = HotkeyListener()

        self._overlay: SelectorOverlay | None = None
        self._editor: EditorWindow | None = None
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
        if self._editor is not None:
            self._editor.close()
        self.qapp.quit()

    # ---- capture flow ----
    def start_capture(self) -> None:
        if self._busy:
            return
        self._busy = True
        try:
            pixmap, rect = grab_virtual_screen()
            self._overlay = SelectorOverlay(pixmap, rect)
            self._overlay.region_selected.connect(self._on_region_selected)
            self._overlay.cancelled.connect(self._on_cancelled)
            self._overlay.destroyed.connect(self._on_overlay_destroyed)
            self._overlay.show()
            self._overlay.raise_()
            self._overlay.activateWindow()
        except Exception as exc:  # pragma: no cover - defensive
            self._busy = False
            QMessageBox.critical(None, "ScreenGrab", f"Capture failed:\n{exc}")

    def _on_region_selected(self, _rect: QRect, cropped: QPixmap) -> None:
        self._open_editor(cropped)

    def _on_cancelled(self) -> None:
        self._busy = False

    def _on_overlay_destroyed(self) -> None:
        self._overlay = None
        # If the editor opened, _busy stays True until that closes.
        if self._editor is None:
            self._busy = False

    def _open_editor(self, cropped: QPixmap) -> None:
        self._editor = EditorWindow(cropped)
        self._editor.destroyed.connect(self._on_editor_destroyed)
        self._editor.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._editor.show()
        self._editor.raise_()
        self._editor.activateWindow()

    def _on_editor_destroyed(self) -> None:
        self._editor = None
        self._busy = False


def main() -> int:
    qapp = QApplication(sys.argv)
    qapp.setApplicationName("ScreenGrab")
    app = ScreenGrabApp(qapp)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
