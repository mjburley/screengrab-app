# ScreenGrab — Install & User Guide

A minimal Windows screenshot tool. Lives in the system tray, capture with **PrintScreen** or a tray click, drag to select a region, then annotate with rectangles, arrows, and text before copying or saving.

---

## Choose your install path

| Path | Best for | Needs Python? |
|---|---|---|
| **A. Pre-built `.exe`** | Most people. Fastest, zero setup. | No |
| **B. From source** | Developers who want to modify/contribute. | Yes (3.11+) |

---

## A) Install from the pre-built `.exe`

1. Go to the **Releases** page of the GitHub repo:
   `https://github.com/mjburley/screengrab-app/releases`
2. Under the latest release, download **`ScreenGrab.exe`**.
3. Move it to a permanent location — recommended:
   ```
   %LOCALAPPDATA%\ScreenGrab\ScreenGrab.exe
   ```
   (i.e. `C:\Users\<you>\AppData\Local\ScreenGrab\`). Create the folder if it doesn't exist. Don't run it from `Downloads` — Windows tags downloaded files and the autostart path will break if you ever clear that folder.
4. Double-click `ScreenGrab.exe`. A red camera icon appears in the system tray, plus a balloon "Running. Press PrintScreen to capture."

> **Windows SmartScreen warning?** First run may show "Windows protected your PC". Click **More info** → **Run anyway**. The .exe is unsigned (no code-signing certificate); Windows learns to trust it after a few launches.

That's it. Skip to **[Using the app](#using-the-app)**.

---

## B) Install from source

### Prerequisites

- **Windows 10 / 11**
- **Python 3.11+** — get it from [python.org](https://www.python.org/downloads/) or the Microsoft Store
- **Git** — get it from [git-scm.com](https://git-scm.com/download/win)

### Steps

```cmd
git clone https://github.com/mjburley/screengrab-app.git
cd screengrab-app
python -m pip install -r requirements.txt
python -m screengrab.main
```

A red camera icon appears in the system tray.

### Build your own `.exe` from source

```cmd
python -m pip install pyinstaller
build.bat
```

The .exe lands in `dist\ScreenGrab.exe` (~240 MB — PySide6 onefile bundles are large).

---

## Using the app

### Capturing

There are three ways to start a capture:

1. **Press PrintScreen** (default global hotkey)
2. **Left-click** the tray icon
3. **Right-click** the tray icon → **Capture**

Then **drag** to draw a rectangle over the area you want. Release to open the editor. Press **Esc** to cancel.

> **PrintScreen does nothing?** Windows 11 hijacks the key for the built-in Snipping Tool. To free it for ScreenGrab:
> **Settings → Accessibility → Keyboard → Use the Print screen key to open Snipping Tool → Off**.
> (Quick path: paste `ms-settings:easeofaccess-keyboard` into the Run dialog.)

### Annotating

The editor toolbar has 5 tool buttons and a 6-colour palette:

```
[▭ Rectangle] [→ Arrow] [T Text]  ⬤⬤⬤⬤⬤⬤  [Copy] [Save]
```

- **Rectangle / Arrow**: click the tool, then drag on the canvas. After release the item is selected and fully drag-droppable. Rectangles get 8 resize handles; arrows get 2 endpoint handles.
- **Text**: click the tool, then click anywhere on the canvas to drop a text box. Type your text, click off to finish. Double-click an existing text box to edit it again.
- **Colour**: click a swatch to set the active colour. If an item is selected, it recolours to match. Default is red.
- **Copy**: copies the annotated image to the clipboard. Paste anywhere with **Ctrl+V**.
- **Save**: writes a PNG to your Downloads folder named `screenshot-YYYYMMDD-HHMMSS.png`. No save dialog — it just saves and confirms in the status bar.

### Keyboard shortcuts (in the editor)

| Key | Action |
|---|---|
| **Esc** | Close the editor without saving |
| **Delete** / **Backspace** | Remove the selected annotation |
| **Ctrl+C** | Copy to clipboard |
| **Ctrl+S** | Save to Downloads |

---

## Auto-start with Windows

Right-click the tray icon → **Start with Windows**. A balloon confirms it's enabled. The app will then launch automatically every time you log in.

To disable, click the same menu item again.

> **Greyed out?** This option only works for the built `.exe`, not when running from `python -m screengrab.main`.

Behind the scenes, this writes `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\ScreenGrab` with the .exe path. You can verify it from a terminal:

```cmd
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v ScreenGrab
```

---

## Uninstall

1. Right-click tray → **Start with Windows** to uncheck (clears the registry entry).
2. Right-click tray → **Quit**.
3. Delete `%LOCALAPPDATA%\ScreenGrab\` (the folder containing `ScreenGrab.exe`).

That's everything — no other files or registry entries are created.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| **PrintScreen does nothing** | Disable the Windows Snipping Tool hijack (see above). |
| **No tray icon appears** | Check the tray overflow area (`^` arrow). Make sure your account has system-tray permissions. |
| **"Couldn't enable autostart"** balloon | The `.exe` is in a path the registry can't reach. Move it to `%LOCALAPPDATA%\ScreenGrab\` and try again. |
| **Editor opens off-screen on multi-monitor** | The editor centres on the primary screen — drag it onto the screen you want. |
| **`.exe` startup is slow (~3 seconds)** | Normal. PyInstaller `--onefile` extracts to a temp dir on every launch. The `--onedir` build mode is faster but produces a folder rather than a single file. |
| **Antivirus flags `ScreenGrab.exe`** | False positive — common for unsigned PyInstaller bundles. Add an exception, or build it yourself from source. |

---

## Reporting bugs

Open an issue at `https://github.com/mjburley/screengrab-app/issues` with:

- Windows version (`winver`)
- Steps to reproduce
- Whether you're running the prebuilt `.exe` or source
