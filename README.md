# ScreenGrab

A minimal Windows screenshot tool. Lives in the system tray; press **PrintScreen** to capture a region of the screen, then annotate with rectangles, arrows, and text before copying or saving.

## Features

- Global **PrintScreen** hotkey
- Drag-to-select any region across one or multiple monitors
- 5 toolbar buttons: **Rectangle**, **Arrow**, **Text**, **Copy**, **Save**
- All annotations are drag-droppable and resizable
- Color palette: Red (default), Black, White, Yellow, Green, Blue
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
