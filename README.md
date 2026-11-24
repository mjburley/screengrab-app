# ScreenGrab

A minimal Windows screenshot tool. Lives in the system tray; press **PrintScreen** to capture a region of the screen, then annotate with rectangles, arrows, and text before copying or saving.

## Features

- Global **PrintScreen** hotkey
- Drag-to-select any region across one or multiple monitors
- Toolbar: **Rectangle**, **Arrow**, **Text** (with a size picker), **Extract Text**, **Copy**, **Save**
- All annotations are drag-droppable and resizable
- **Extract Text**: drag over part of the screenshot, or click once for all of it, to copy its text to the clipboard. It uses the OCR engine built into Windows and works offline.
- Take several screenshots in a row: press PrintScreen again while editors are open. They hide while you select, then come back, and each capture gets its own editor.
- Color palette: Red (default), Black, White, Yellow, Green, Blue
- Follows Windows light or dark mode, including switching while an editor is open
- Save to `%USERPROFILE%\Downloads\screenshot-YYYYMMDD-HHMMSS.png`

## Run from source

```
pip install -r requirements.txt
python -m screengrab.main
```

A tray icon appears. Press **PrintScreen** to capture, or right-click the tray icon and choose **Capture**.

## Build a standalone .exe

```
pip install pyinstaller
build.bat
```

The executable is written to `dist\ScreenGrab.exe`.

## Editor shortcuts

| Key | Action |
|---|---|
| **Esc** (during region select) | Cancel capture |
| **Esc** (in editor) | Close without saving |
| **Delete** | Remove selected annotation |
| **Ctrl+C** | Copy to clipboard |
| **Ctrl+S** | Save to Downloads |
| **Ctrl+Shift+C** | Extract all text to clipboard |
