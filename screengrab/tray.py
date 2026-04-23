"""System tray icon with Capture / Start-with-Windows / Quit menu."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from . import autostart


def _build_default_icon() -> QIcon:
    """Generate a simple round red 'camera dot' tray icon at runtime."""
    pm = QPixmap(32, 32)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(220, 38, 38))
    p.setPen(QColor(255, 255, 255))
    p.drawRoundedRect(3, 8, 26, 18, 4, 4)
    p.setBrush(QColor(255, 255, 255))
    p.drawEllipse(11, 12, 10, 10)
    p.setBrush(QColor(220, 38, 38))
    p.drawEllipse(13, 14, 6, 6)
    p.end()
    return QIcon(pm)


class Tray(QObject):
    capture_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.icon = QSystemTrayIcon(_build_default_icon(), parent=self)
        self.icon.setToolTip("ScreenGrab — press PrintScreen to capture")

        menu = QMenu()
        act_capture = QAction("Capture", menu)
        act_capture.triggered.connect(self.capture_requested)
        menu.addAction(act_capture)

        menu.addSeparator()
        self.act_autostart = QAction("Start with Windows", menu)
        self.act_autostart.setCheckable(True)
        if autostart.is_frozen():
            self.act_autostart.setChecked(autostart.is_enabled())
            self.act_autostart.toggled.connect(self._on_autostart_toggled)
        else:
            self.act_autostart.setEnabled(False)
            self.act_autostart.setToolTip(
                "Available only when running the built ScreenGrab.exe"
            )
        menu.addAction(self.act_autostart)

        menu.addSeparator()
        act_quit = QAction("Quit", menu)
        act_quit.triggered.connect(self.quit_requested)
        menu.addAction(act_quit)

        self._menu = menu
        self.icon.setContextMenu(menu)
        self.icon.activated.connect(self._on_activated)

    def show(self) -> None:
        self.icon.show()

    def notify(self, title: str, body: str) -> None:
        self.icon.showMessage(title, body, QSystemTrayIcon.MessageIcon.Information, 2500)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        # Left-click triggers capture; right-click already shows menu.
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.capture_requested.emit()

    def _on_autostart_toggled(self, checked: bool) -> None:
        if checked:
            ok = autostart.enable()
            if ok:
                self.notify("ScreenGrab", "Will start with Windows.")
            else:
                # Revert checkbox if we couldn't write the registry key.
                self.act_autostart.blockSignals(True)
                self.act_autostart.setChecked(False)
                self.act_autostart.blockSignals(False)
                self.notify("ScreenGrab", "Couldn't enable autostart.")
        else:
            autostart.disable()
            self.notify("ScreenGrab", "Will no longer start with Windows.")
