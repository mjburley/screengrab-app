# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```cmd
:: install deps (use --user if system pip is broken). Python 3.11+ (dev machine: 3.12)
python -m pip install -r requirements.txt
:: PyInstaller is NOT in requirements.txt — build.bat exits early without it
python -m pip install --user pyinstaller

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

PowerShell equivalent of the replace-install step (the cmd block above won't run in PowerShell or Git Bash as-is):

```powershell
Stop-Process -Name ScreenGrab -Force -ErrorAction SilentlyContinue
Copy-Item dist\ScreenGrab.exe "$env:LOCALAPPDATA\ScreenGrab\ScreenGrab.exe" -Force
Start-Process "$env:LOCALAPPDATA\ScreenGrab\ScreenGrab.exe"
```

There is no test suite, linter, or formatter configured. To verify a change, run it and capture something. **Quit the installed tray instance first.** Both instances hook PrintScreen through pynput without suppressing the key, so both would respond. Left-clicking the tray icon also starts a capture.

`ScreenGrab.spec` is a generated file (gitignored). PyInstaller rewrites it on every build because `build.bat` passes all options on the command line, so put build changes in `build.bat`, not the spec.

**Headless checks:** `QT_QPA_PLATFORM=offscreen` lets you construct `EditorWindow`, drive it with `QTest`, and read the clipboard without touching the real desktop. You must also set `QT_QPA_FONTDIR=C:/Windows/Fonts`. Without it, offscreen Qt has no fonts, every glyph renders as a box, and OCR returns strings like `0000…`. Run with `PYTHONPATH=.` when the test script is outside the repo.

**Visual/theme checks:** offscreen ignores the Windows light/dark setting. Instead keep the real platform, construct the window without showing it, and save `widget.grab()` to a PNG. Force a scheme with `QGuiApplication.styleHints().setColorScheme(Qt.ColorScheme.Dark)` (Qt 6.8+), set before building the window, or after it to test a live switch.

If PySide6 imports fail with `libshiboken does not exist`, shiboken6 didn't install: `python -m pip install --user --force-reinstall --no-deps shiboken6 PySide6`.

## Deploy and release

- **"Deploy"** means: rebuild, replace `%LOCALAPPDATA%\ScreenGrab\ScreenGrab.exe`, relaunch it, then confirm the tray icon appears and a capture works.
- **User-visible changes** also need `README.md` (Features list + Editor shortcuts table) and `INSTALL.md` ("Using the app" + keyboard shortcuts) updated in the same commit.
- **Release:** bump `__version__` in `screengrab/__init__.py` (its only definition; nothing else reads it), commit and push, then publish a GitHub Release tagged `vX.Y.Z` on `main` with the .exe attached: `gh release create vX.Y.Z dist\ScreenGrab.exe --title "vX.Y.Z — <summary>"`. `INSTALL.md` sends users to the repo's Releases page (`mjburley/screengrab-app`). Tags only exist on the remote because `gh` creates them.

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

`ScreenGrabApp` (in `screengrab/main.py`) owns the lifecycle, and `setQuitOnLastWindowClosed(False)` keeps the process alive after editors close.

**Multiple editors, one capture at a time.**

- `_editors` holds every open `EditorWindow`. Each removes itself via `destroyed`. New ones open centred, then shift 30,30 per already-open editor, wrapping after 8 (`len(_editors) % 8`).
- `_busy` covers a single capture only: hide editors, grab, overlay.
- `start_capture` hides visible editors (into `_hidden`) so they aren't in the new screenshot, the way Snipping Tool does. It then waits `HIDE_DELAY_MS` before grabbing.
- Hidden editors are restored on `region_selected` (before the new editor opens, so the new one lands on top), on `cancelled`, and as a safety net on overlay `destroyed`.
- `_busy` clears **only** on overlay `destroyed`. That always fires, because the overlay closes on every path (select, Esc, right-click, tiny drag) and is `WA_DeleteOnClose`. Clearing it on `cancelled` instead would let a stale `destroyed` from the old overlay reset state while a new overlay is open.

### Key invariants

- **No persisted state.** The app writes only the `HKCU\...\Run\ScreenGrab` value (autostart) and PNGs the user saves to Downloads. INSTALL.md's Uninstall section promises this, so don't add `QSettings`, config files or logs without updating INSTALL.md.
- **Per-monitor DPI awareness must be set BEFORE `QApplication` is constructed.** `main.py` calls `ctypes.windll.shcore.SetProcessDpiAwareness(2)` and `setHighDpiScaleFactorRoundingPolicy(PassThrough)` at module top. PyInstaller-built .exes default to system-DPI awareness — without this, 4K/scaled displays render the overlay at the wrong size.
- **DPR juggling.** `capture.grab_virtual_screen()` returns the physical-pixel pixmap tagged with `setDevicePixelRatio(dpr)`, plus a logical-unit `QRect` from `QScreen.virtualGeometry()`. `SelectorOverlay` is sized in logical units but converts mouse coords to physical pixels before passing them to `QPixmap.copy()` / `drawPixmap` source rects (Qt expects physical pixels there regardless of DPR). The cropped pixmap handed to the editor has DPR stripped to 1.0 so editor/export math stays simple.
- **Single DPR for the whole desktop.** `grab_virtual_screen()` takes the **primary** screen's `devicePixelRatio` and applies it to the entire mss capture. This assumes every monitor uses the same Windows scaling. On mixed-scaling setups (for example a 150% laptop plus a 100% external monitor), suspect this first if crops are offset or mis-sized. Separately, the overlay covers the monitors' bounding rect, so gaps between offset monitors are selectable but invisible. DEVELOPMENT.md treats that as known and cosmetic.
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

To add an annotation tool, change all of these:

1. Add a `ToolMode` member in `tools.py`.
2. Add an item class in `items.py`. It must implement `set_color(QColor)` and `color()`, because swatch clicks recolour selected items with a `hasattr(item, "set_color")` check.
3. Add creation branches in `EditorView.mousePressEvent`, `mouseMoveEvent` and `mouseReleaseEvent`. Release drops degenerate items (rectangles under 4 px, arrows under 6 px) and then calls `set_tool(SELECT)`. Text is the exception: it switches back to SELECT on press and goes straight into edit mode.
4. Add a checkable button in `EditorWindow._build_toolbar` and its checked-state line in `set_tool`.

Text size works like colour. `EditorWindow.active_text_size` applies to new `TextItem`s, and picking a size also resizes the selected text items. The combo uses `activated` rather than `currentIndexChanged`, so re-picking the size already shown still applies it. The last size is kept in a class attribute (`_remembered_text_size`) and lasts until the tray app quits. It is deliberately not written to `QSettings` (see "No persisted state" above).

**Dark mode.** Qt's `windows11` style (PySide6 6.11 here) follows the Windows light/dark setting, but the editor toolbar is drawn by a stylesheet, which overrides the palette:

- `editor.THEMES` sets every colour for both schemes, text included. A stylesheet that sets a background without `color:` gives white-on-white text in dark mode (the v0.2.0 bug).
- `_apply_theme` re-runs on `styleHints().colorSchemeChanged`, so open editors switch live. It also redraws the active-swatch ring, which is black in light mode and white in dark mode.
- The size combo is deliberately left unstyled: a partial `QComboBox` rule leaves a stray native border around its arrow.

### Extract Text (OCR)

`ocr.extract_text(QImage)` calls Windows' built-in `Windows.Media.Ocr` through the pywinrt `winrt-*` packages. It needs no external binary and uses the OCR model for the user's display language.

In the editor, Extract Text is a **tool** (`ToolMode.OCR`), not an action button:

- `EditorView` draws a temporary `QGraphicsRectItem` band. The band is not an annotation and is removed on release.
- On release the view calls `EditorWindow.extract_text(region)`. A click under 4px means `region=None`, the whole screenshot. Ctrl+Shift+C calls `extract_text()` directly.
- A hint shows in the status bar while the tool is active, and `set_tool` clears it.
- `extract_text` crops the **original capture** (`bg_item.pixmap()`), not the annotated render, and guards empty crops. `QPixmap.copy()` with an empty rect copies the *whole* pixmap, so a drag entirely outside the image would otherwise OCR everything.

Inside `ocr.py`:

- **Padding is essential.** Windows OCR returns *nothing* for text cropped snugly to its edges (tested at 9–14pt, light and dark). `_pad` adds a 16px border in the image's most common edge colour first; 8px was the minimum that worked.
- Images are upscaled 2×, capped at `OcrEngine.max_image_dimension` (10000). Small text is misread at 1:1, and very wide multi-monitor captures get scaled down instead.
- It runs synchronously on the UI thread behind a wait cursor. A 5120×1440 desktop takes about 0.5 s. `asyncio.run` is safe there because Qt doesn't run an asyncio loop.
- It works under Qt's COM STA on the main thread and also from worker threads.
- Known OCR misreads: `£` and slashed zeros (`Ø`). This is an engine limitation, not a bug in our code.
- **PyInstaller:** `winrt-runtime` registers its own hook (`pyinstaller40` entry point). The hook collects every installed `winrt-*` projection and its `_table.pywinrt` data file, so no build flags are needed. If the frozen app reports "Windows OCR support is missing from this build", the build environment lacks the winrt packages.

The editor's minimum width comes from the toolbar's `sizeHint`, so more buttons widen it automatically. That is what keeps Copy/Save visible on narrow screenshots.

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
| `screengrab/tools.py` | `ToolMode` enum, `PALETTE` (colours) and `TEXT_SIZES` / `DEFAULT_TEXT_SIZE`; the single source of truth for both. |
| `screengrab/hotkey.py` | `pynput` PrintScreen listener on a daemon thread; emits Qt signal (queued connection marshals to UI thread). |
| `screengrab/tray.py` | `QSystemTrayIcon` + menu; programmatically generated icon. |
| `screengrab/export.py` | Render scene → clipboard / PNG (timestamped, to `~\Downloads`). |
| `screengrab/ocr.py` | Windows built-in OCR (`Windows.Media.Ocr`) → plain text; raises `OcrError` with a user-readable message. |
| `screengrab/autostart.py` | `winreg` wrapper for `HKCU\...\Run\ScreenGrab`; refuses when not frozen. |
| `run_screengrab.py` | Top-level launcher for PyInstaller. |
| `build.bat` | PyInstaller invocation; conditionally adds `--icon` if `assets\tray.ico` exists. |

## Platform notes

- **Windows-only.** `winreg`, `ctypes.windll.shcore`, and the PrintScreen hotkey expectation are Windows-specific.
- **Windows 11 hijacks PrintScreen** for the Snipping Tool by default. Users must disable it via Settings → Accessibility → Keyboard. There's no programmatic bypass.
- **Git Bash gotcha:** invoking `cmd /c build.bat` from MSYS shells fails due to path-translation quoting. Prefer `python -m PyInstaller ...` directly. Single-char flags need double slashes in Git Bash (`taskkill //F //IM ...`).

## Things deliberately not implemented (per DEVELOPMENT.md)

Undo/redo, save-as dialog, settings UI, hotkey rebind, code signing, auto-update, additional tools (pen/blur/ellipse). Delete/Backspace removal is the only annotation reversal.
