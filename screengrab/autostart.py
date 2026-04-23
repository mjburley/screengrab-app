"""Manage 'Start with Windows' via the per-user Run registry key.

We only enable autostart when the app is running as a frozen PyInstaller .exe;
launching the source-mode ``python -m screengrab.main`` on every login isn't a
useful default and the path would be brittle.
"""
from __future__ import annotations

import sys
import winreg
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "ScreenGrab"


def is_frozen() -> bool:
    """True when running from a PyInstaller-built .exe."""
    return bool(getattr(sys, "frozen", False))


def executable_path() -> Path | None:
    """Return the absolute .exe path if frozen, else None."""
    if not is_frozen():
        return None
    return Path(sys.executable).resolve()


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(value)
    except FileNotFoundError:
        return False
    except OSError:
        return False


def enable() -> bool:
    """Add the Run entry pointing at the current .exe. Returns True on success."""
    exe = executable_path()
    if exe is None:
        return False
    # Wrap path in quotes to survive spaces.
    command = f'"{exe}"'
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
    ) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
    return True


def disable() -> None:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, APP_NAME)
    except FileNotFoundError:
        pass
