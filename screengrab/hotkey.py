"""Global PrintScreen listener using pynput.

Runs the listener on a daemon thread; emits a Qt signal that is delivered to
the main thread via Qt::QueuedConnection (Signal/slot already does this when
the receiver lives in the main thread).
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from pynput import keyboard


class HotkeyListener(QObject):
    triggered = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._listener: keyboard.Listener | None = None

    def start(self) -> None:
        if self._listener is not None:
            return
        self._listener = keyboard.Listener(on_press=self._on_press)
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def _on_press(self, key) -> None:
        # PrintScreen reports as Key.print_screen on Windows via pynput.
        if key == keyboard.Key.print_screen:
            self.triggered.emit()
