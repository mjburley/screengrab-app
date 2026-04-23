# ScreenGrab — Development Notes

A retrospective of how this app was built: the design choices, the surprises, the dead-ends, and the patterns worth remembering.

---

## What got built

A Windows screenshot tool with these features, in roughly this build order:

1. **Capture pipeline** — `mss` grabs the virtual desktop into a `QPixmap`; a frameless overlay covering all monitors lets the user drag-select a region.
2. **Editor** — `QGraphicsView` + `QGraphicsScene` shows the cropped screenshot with a top toolbar.
3. **Annotations** — three custom `QGraphicsItem` subclasses: rectangle (with 8 resize handles), arrow (with 2 endpoint handles), text (double-click to edit). All are drag-droppable for free thanks to Qt flags.
4. **Colour palette** — six swatches; clicking one sets the active colour for new items and recolours the currently selected item.
5. **Export** — render the scene to a `QImage`, then either push to clipboard or save a timestamped PNG to `~\Downloads\`.
6. **System tray** — `QSystemTrayIcon` with a generated red-camera icon; menu has Capture / Start-with-Windows / Quit.
7. **Global hotkey** — `pynput` listener on a daemon thread, emits a Qt signal when PrintScreen is pressed.
8. **Autostart toggle** — checkbox in the tray menu writes/clears `HKCU\...\Run\ScreenGrab` via `winreg`.
9. **Packaging** — PyInstaller `--onefile --noconsole` produces `dist\ScreenGrab.exe` (~243 MB), copied to `%LOCALAPPDATA%\ScreenGrab\` for stable autostart paths.

---

## Tech stack rationale

| Choice | Reason | Alternative considered |
|---|---|---|
| **Python 3.12 + PySide6** | Qt's `QGraphicsScene` gives free drag/select/move on items — no custom hit-testing. PySide6 is LGPL (no licence cost). | C# WPF (Windows-native, faster startup); Electron (heavy); tkinter (too primitive for resizable graphics). |
| **mss** | Multi-monitor screen capture in one call, no Win32 boilerplate. Fast (uses `BitBlt` under the hood). | `PIL.ImageGrab.grab(all_screens=True)` — slower and the API is awkward for the bbox case. |
| **pynput** for global hotkey | Doesn't require admin (unlike the `keyboard` library on Windows). | `keyboard` (admin), `RegisterHotKey` via pywin32 (more code, no benefit here). |
| **PyInstaller `--onefile`** | One file to distribute. Trade-off: cold start ~3s while it extracts. | `--onedir` (faster startup, ugly folder); Briefcase (more setup). |

---

## Architecture at a glance

```
PrintScreen ──► HotkeyListener (daemon thread)
                    │ Qt signal (queued, marshals to UI thread)
                    ▼
           ScreenGrabApp.start_capture()
                    │
                    ├─ capture.grab_virtual_screen()  ─► QPixmap of whole desktop
                    │
                    └─ SelectorOverlay (frameless, top-most, full virtual-screen)
                            │ region_selected(QRect, cropped QPixmap)
                            ▼
                       EditorWindow
                       ├─ QGraphicsScene (background pixmap + annotations)
                       ├─ Toolbar (5 buttons + 6 swatches)
                       └─ Copy / Save → export.render_scene() → clipboard or PNG
```

**Single source of state** for tools and active colour lives on `EditorWindow` (`active_tool`, `active_color`). `EditorView.mousePressEvent` reads them to decide what to do on click. Tool reverts to `SELECT` immediately after creating an item — so the new item is draggable without a second click.

**Why `QGraphicsScene` was the right choice**: every annotation is a `QGraphicsItem` with three flags set:

```python
item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
```

That alone delivers the entire "all drag-droppable" requirement — Qt does the mouse math, focus tracking, and rubber-band selection for free. The only custom code is for the *resize* handles (8 on rectangles, 2 endpoints on arrows), which involves overriding `paint`, `mousePressEvent`, and `mouseMoveEvent` to detect handle hits and update geometry.

---

## What went wrong (and how it was fixed)

These are the moments worth remembering — each one cost real time.

### 1. Broken Python install on the host

`pip install -r requirements.txt` failed with:
```
ERROR: Could not install packages due to an OSError: [WinError 2]
The system cannot find the file specified: 'C:\Python312\Scripts\mss.exe'
```

The global `C:\Python312\` site-packages was in a partially-broken state (a previous `pip uninstall` had been interrupted). Fix: `pip install --user` to bypass the system-level write entirely. The user-site lives at `%APPDATA%\Python\Python312\`.

**Lesson**: when system-pip is broken, `--user` is faster than diagnosing why.

### 2. PySide6 installed without `shiboken6`

After the workaround above:
```
ImportError: ...\shiboken6\libshiboken does not exist
```

PySide6 imports failed because shiboken6 (the C++/Python bindings layer) hadn't installed. Cause: pip's resolver had walked away from the broken install before reaching shiboken6.

Fix: `pip install --user --force-reinstall --no-deps shiboken6 PySide6`.

**Lesson**: PySide6 is two packages — if PySide6 imports fail mysteriously, check for `shiboken6` first.

### 3. `cmd /c build.bat` didn't run from Git Bash

Calling `cmd /c build.bat` (or even `cmd /c "<absolute path>\build.bat"`) from Git Bash failed with "build.bat is not recognized". MSYS path translation was mangling the argument quoting.

Fix: skip the `.bat` and call PyInstaller directly via `python -m PyInstaller ...`. Updated the `.bat` to do the same so it works regardless of caller. Also: in Git Bash, single-character flags need *double* slashes — `taskkill //F //IM ScreenGrab.exe`, not `/F /IM`.

**Lesson**: prefer `python -m <package>` over the entry-point script when invoking from cross-shell scripts.

### 4. PyInstaller broke relative imports

First build succeeded, but `ScreenGrab.exe` crashed instantly:
```
ImportError: attempted relative import with no known parent package
```

Root cause: PyInstaller was given `screengrab/main.py` as the entry script. It runs that as a top-level script (not as `screengrab.main`), so `from .capture import ...` blows up.

Fix: created `run_screengrab.py` at the project root:
```python
from screengrab.main import main
import sys
if __name__ == "__main__":
    sys.exit(main())
```

Pointed PyInstaller at `run_screengrab.py` instead. Now the package is imported normally and relative imports work.

**Lesson**: when building a Python package as an exe, always go through a top-level launcher script. Never feed a module-inside-a-package directly to PyInstaller.

### 5. Windows 11 hijacks PrintScreen

The hotkey listener worked fine — but the user reported PrintScreen did nothing. Cause: Win11 has a setting that intercepts PrintScreen *before* any third-party app sees it, in order to launch the built-in Snipping Tool.

Fix path: **Settings → Accessibility → Keyboard → Use the Print screen key to open Snipping Tool → Off**. There's no programmatic way to bypass this — Microsoft owns the OS-level shortcut.

**Lesson**: on Windows 11, `Win+Shift+S` and `PrintScreen` are both reserved by the Snipping Tool. Document this in the user guide.

### 6. `Qt.Tool` windows don't take keyboard focus

The selector overlay's `keyPressEvent` correctly handled `Esc` to cancel — but pressing Esc did nothing in practice. The overlay was created with `Qt.WindowType.Tool`, which on Windows tells the WM "this is a utility window, don't give it focus".

Fix: in `SelectorOverlay.showEvent`, call `activateWindow()`, `setFocus()`, **and** `grabKeyboard()` (the last one bypasses focus entirely — every key event is delivered to the widget that called `grabKeyboard`). Pair it with `releaseKeyboard()` in `closeEvent` so we don't leak the grab.

```python
def showEvent(self, event):
    super().showEvent(event)
    self.activateWindow()
    self.raise_()
    self.setFocus(Qt.FocusReason.OtherFocusReason)
    self.grabKeyboard()  # belt and braces
```

**Lesson**: `Qt.Tool` is great for keeping a window off the taskbar but it's hostile to keyboard input. Use `grabKeyboard()` for any modal-ish overlay where keys must be captured.

### 7. Autostart needs a *stable* path

Initial build wrote the dev path (`...\ScreenGrab App\dist\ScreenGrab.exe`) into the registry. That's fine until the user moves or rebuilds the project — Windows then silently fails to launch the app at login.

Fix: copy the .exe to `%LOCALAPPDATA%\ScreenGrab\` (a path Windows considers stable for per-user binaries), launch from there, and let the autostart toggle write *that* path.

**Lesson**: registry Run entries pin a path; treat the .exe location like an installed binary, not a build artifact. `%LOCALAPPDATA%` is the right home for unprivileged installs.

### 8. High-DPI / 4K monitors looked broken

On a 4K display with Windows scaling (150% or 200%), the overlay went weird — the captured desktop appeared at the wrong scale and the whole screen looked like it had switched resolution. Two stacked problems:

1. **PyInstaller .exes default to system-DPI awareness**, so when launched on a per-monitor-DPI-aware Windows, Qt was being lied to about the screen scale.
2. **mss captures at physical pixels**, but Qt sizes windows in device-independent (logical) units. Setting `setGeometry(physical_rect)` made the overlay too large; drawing the physical-sized pixmap into a logical-sized widget produced visual nonsense.

Fix:
- At process start (before `QApplication`): `ctypes.windll.shcore.SetProcessDpiAwareness(2)` for per-monitor V2, plus `setHighDpiScaleFactorRoundingPolicy(PassThrough)` to handle fractional 150%-style scaling.
- `capture.grab_virtual_screen()` now returns `(pixmap, logical_rect, dpr)` — the pixmap is tagged with `setDevicePixelRatio(dpr)`, the rect uses Qt's `virtualGeometry()` (device-independent units).
- `SelectorOverlay` accepts `dpr` and converts logical mouse coordinates to physical pixels before calling `QPixmap.copy()` / passing `source` to `drawPixmap()` (Qt expects physical pixel units in those source rects, regardless of DPR).
- The cropped pixmap handed to the editor has DPR stripped to 1.0, so the editor and export pipeline keep their simple "1 pixel = 1 unit" maths.

**Lesson**: high-DPI in Qt is two separate problems — telling Windows you're DPI-aware (an OS-level flag baked into the manifest, or set at runtime via `SetProcessDpiAwareness`), and then juggling the difference between device-independent units (most Qt APIs) and physical pixels (`QPixmap.copy`, `drawPixmap` source rects). Get either wrong and the whole UI looks broken.

---

## File-by-file responsibilities

| File | Purpose | Notes |
|---|---|---|
| `screengrab/main.py` | App entry. Wires tray, hotkey, capture flow. | `setQuitOnLastWindowClosed(False)` keeps the process alive when the editor closes. |
| `screengrab/tray.py` | `QSystemTrayIcon` + menu. Generates its icon programmatically (no asset file). | Autostart toggle is greyed out unless `autostart.is_frozen()`. |
| `screengrab/hotkey.py` | `pynput` PrintScreen listener on a daemon thread. | Emits a Qt signal — Qt's signal/slot machinery marshals to the UI thread automatically (queued connection). |
| `screengrab/capture.py` | `mss` → `QPixmap` of the virtual desktop. | `mss.monitors[0]` is the bounding rect of all monitors (handy for overlays). |
| `screengrab/selector.py` | Frameless drag-to-select overlay. | Grabs keyboard so Esc works. Re-paints the captured pixmap inside the selection rect at full brightness. |
| `screengrab/editor.py` | Toolbar + canvas + tool/colour state. | View intercepts mouse to create items in tool modes; reverts to SELECT on release. |
| `screengrab/items.py` | `MovableRectItem`, `ArrowItem`, `TextItem`. | Custom resize/endpoint handles are drawn in `paint` and hit-tested in `mousePressEvent`. |
| `screengrab/tools.py` | `ToolMode` enum, `PALETTE` colour list. | Single source of truth for colours. |
| `screengrab/export.py` | Render scene → clipboard / PNG. | Temporarily deselects items so handles don't appear in output. |
| `screengrab/autostart.py` | `winreg` wrapper for the Run key. | Refuses to enable when not frozen — protects against pinning the source-mode python.exe path. |
| `run_screengrab.py` | Top-level entry for PyInstaller. | Imports the package so relative imports work. |
| `build.bat` | PyInstaller invocation. | Uses `python -m PyInstaller`; conditionally adds `--icon` if `assets\tray.ico` exists. |

---

## Build & deploy workflow

```cmd
:: rebuild
python -m PyInstaller --noconfirm --onefile --noconsole ^
    --name ScreenGrab --collect-submodules PySide6 -p . run_screengrab.py

:: stop running instance, replace the installed copy, relaunch
taskkill /F /IM ScreenGrab.exe
copy /Y dist\ScreenGrab.exe "%LOCALAPPDATA%\ScreenGrab\ScreenGrab.exe"
start "" "%LOCALAPPDATA%\ScreenGrab\ScreenGrab.exe"
```

`--collect-submodules PySide6` is essential — PyInstaller's static analysis misses many Qt submodules otherwise, and the bundle silently fails when something tries to load them at runtime.

---

## Things deliberately *not* done

These were considered and intentionally left out to keep v1 scoped:

- **Undo/redo stack** — Delete key removes selected items; that's the only mutation reversal. A `QUndoStack` would be the right primitive if added later.
- **More tools** — pen/highlighter, blur, ellipse, numbered markers. All are easy `QGraphicsItem` subclasses to add.
- **Save As dialog** — always saves to Downloads. Adding an option dialog or a "default save location" setting is a sensible follow-up.
- **Settings UI** — colour palette and hotkey are hard-coded. A `QSettings`-backed dialog with hotkey rebind would be the next reasonable addition.
- **Code signing** — unsigned `.exe` triggers SmartScreen warnings. Signing requires a paid certificate.
- **Auto-update** — no update checker. PyUpdater or a simple version-ping would work.
- **Multi-monitor selector edge cases** — the overlay covers the bounding rect of all monitors but doesn't handle gaps (e.g. monitors at different vertical positions). The blank "L-shaped" gap area is paintable but not visible to the user, so this is mostly cosmetic.

---

## Patterns worth keeping

A few small choices that made the code easier to live with:

1. **Generate the tray icon at runtime** with `QPainter` instead of shipping a `.png`. No asset pipeline, no `--add-data` flag in PyInstaller, no missing-icon failures.
2. **Tool mode reverts to `SELECT` after each shape creation**. Means the user can immediately drag the just-drawn item without an extra click. Small touch, big difference in feel.
3. **Hide selection chrome before rendering**. `export.render_scene` deselects items, renders, then re-selects — so handles never appear in the output PNG.
4. **`setAttribute(WA_DeleteOnClose)`** on transient windows (overlay, editor). No manual cleanup needed; closing the window frees its memory.
5. **Daemon thread for `pynput`**. Listener thread doesn't keep the process alive; quitting the app cleanly stops the hotkey hook.

---

## Total LOC

```
screengrab/  ~600 lines (excluding blank lines and comments)
```

Modest size for the feature surface — Qt does most of the heavy lifting.
