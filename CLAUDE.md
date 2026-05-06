# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```cmd
:: install deps (use --user if system pip is broken)
python -m pip install -r requirements.txt

:: run from source — relative imports require -m, NOT `python screengrab/main.py`
python -m screengrab.main

:: build standalone .exe (output: dist\ScreenGrab.exe, ~240 MB)
build.bat
:: equivalent direct invocation:
python -m PyInstaller --noconfirm --onefile --noconsole ^
    --name ScreenGrab --collect-submodules PySide6 -p . run_screengrab.py

:: replace a running install
taskkill /F /IM ScreenGrab.exe
copy /Y dist\ScreenGrab.exe "%LOCALAPPDATA%\ScreenGrab\ScreenGrab.exe"
start "" "%LOCALAPPDATA%\ScreenGrab\ScreenGrab.exe"
```

There is no test suite, linter, or formatter configured.

## Architecture

Single-process Qt app (PySide6) that lives in the system tray. The capture pipeline is:

```
PrintScreen / tray click ─► HotkeyListener (pynput, daemon thread)
                              │ Qt signal — queued, marshals to UI thread
                              ▼
                  ScreenGrabApp.start_capture()  (main.py)
                              │
                              ├─ capture.grab_virtual_screen()  → (QPixmap, logical QRect, dpr)
                              │
                              └─ SelectorOverlay (frameless, top-most, full virtual desktop)
                                      │ region_selected(QRect, cropped QPixmap)
                                      ▼
                                EditorWindow (QGraphicsScene + toolbar)
                                      │
                                      └─ export.render_scene → clipboard or PNG in ~\Downloads
```

`ScreenGrabApp` (in `screengrab/main.py`) owns the lifecycle: `_busy` flag prevents overlapping captures, and `setQuitOnLastWindowClosed(False)` keeps the process alive after the editor closes.

### Key invariants

- **Per-monitor DPI awareness must be set BEFORE `QApplication` is constructed.** `main.py` calls `ctypes.windll.shcore.SetProcessDpiAwareness(2)` and `setHighDpiScaleFactorRoundingPolicy(PassThrough)` at module top. PyInstaller-built .exes default to system-DPI awareness — without this, 4K/scaled displays render the overlay at the wrong size.
- **DPR juggling.** `capture.grab_virtual_screen()` returns the physical-pixel pixmap tagged with `setDevicePixelRatio(dpr)`, plus a logical-unit `QRect` from `QScreen.virtualGeometry()`. `SelectorOverlay` is sized in logical units but converts mouse coords to physical pixels before passing them to `QPixmap.copy()` / `drawPixmap` source rects (Qt expects physical pixels there regardless of DPR). The cropped pixmap handed to the editor has DPR stripped to 1.0 so editor/export math stays simple.
- **PyInstaller entry point is `run_screengrab.py`, NOT `screengrab/main.py`.** Pointing PyInstaller at a module-inside-a-package breaks relative imports (`from .capture import ...`). The launcher imports the package so relative imports resolve.
- **`--collect-submodules PySide6` is required.** PyInstaller's static analysis misses Qt submodules; without this the bundle silently fails at runtime.
- **Autostart only enables when frozen.** `autostart.is_frozen()` gates the Run-key write so source-mode runs don't pin a `python.exe` path. The .exe should live at a stable path (`%LOCALAPPDATA%\ScreenGrab\`) — the registry pins absolute paths, so the dev-tree `dist\` location is the wrong target.

### Editor / annotations

`EditorWindow` (`editor.py`) holds the single source of truth for `active_tool` and `active_color`. `EditorView.mousePressEvent` reads them to decide what to do; the tool reverts to `SELECT` immediately after creating an item so it's draggable without an extra click.

Annotations (`items.py`) are `QGraphicsItem` subclasses: `MovableRectItem` (8 resize handles), `ArrowItem` (2 endpoint handles), `TextItem`. Drag/select/move come for free from these flags:

```python
ItemIsMovable | ItemIsSelectable | ItemSendsGeometryChanges
```

Custom code is only for resize/endpoint handles (drawn in `paint`, hit-tested in `mousePressEvent`). `export.render_scene` deselects all items before rendering so handles never appear in the output PNG.

### Selector overlay focus quirk

`SelectorOverlay` is a `Qt.WindowType.Tool` window, which on Windows refuses keyboard focus. To make Esc work, `showEvent` calls `activateWindow()`, `setFocus()`, AND `grabKeyboard()` (the last one bypasses focus entirely); `closeEvent` must call `releaseKeyboard()` to avoid leaking the grab.

### Tray icon

Generated at runtime with `QPainter` (`tray.py`) — no `.png` asset shipped, no `--add-data` in PyInstaller, no missing-icon failures.

## File responsibilities

| File | Purpose |
|---|---|
| `screengrab/main.py` | Entry point. DPI setup, `ScreenGrabApp` wiring tray + hotkey + capture flow. |
| `screengrab/capture.py` | `mss` → `QPixmap` of the virtual desktop, with DPR tagging. |
| `screengrab/selector.py` | Frameless drag-to-select overlay; converts logical mouse coords ↔ physical pixels. |
| `screengrab/editor.py` | Toolbar + canvas + tool/colour state. |
| `screengrab/items.py` | `QGraphicsItem` subclasses with custom resize/endpoint handles. |
| `screengrab/tools.py` | `ToolMode` enum + `PALETTE` (single source of truth for colours). |
| `screengrab/hotkey.py` | `pynput` PrintScreen listener on a daemon thread; emits Qt signal (queued connection marshals to UI thread). |
| `screengrab/tray.py` | `QSystemTrayIcon` + menu; programmatically generated icon. |
| `screengrab/export.py` | Render scene → clipboard / PNG (timestamped, to `~\Downloads`). |
| `screengrab/autostart.py` | `winreg` wrapper for `HKCU\...\Run\ScreenGrab`; refuses when not frozen. |
| `run_screengrab.py` | Top-level launcher for PyInstaller. |
| `build.bat` | PyInstaller invocation; conditionally adds `--icon` if `assets\tray.ico` exists. |

## Platform notes

- **Windows-only.** `winreg`, `ctypes.windll.shcore`, and the PrintScreen hotkey expectation are Windows-specific.
- **Windows 11 hijacks PrintScreen** for the Snipping Tool by default. Users must disable it via Settings → Accessibility → Keyboard. There's no programmatic bypass.
- **Git Bash gotcha:** invoking `cmd /c build.bat` from MSYS shells fails due to path-translation quoting. Prefer `python -m PyInstaller ...` directly. Single-char flags need double slashes in Git Bash (`taskkill //F //IM ...`).

## Things deliberately not implemented (per DEVELOPMENT.md)

Undo/redo, save-as dialog, settings UI, hotkey rebind, code signing, auto-update, additional tools (pen/blur/ellipse). Delete-key removal is the only annotation reversal.
