@echo off
setlocal
pushd "%~dp0"

python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Install with: python -m pip install --user pyinstaller
    exit /b 1
)

set ICON_FLAG=
if exist assets\tray.ico set ICON_FLAG=--icon assets\tray.ico

python -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --noconsole ^
    --name ScreenGrab ^
    %ICON_FLAG% ^
    --collect-submodules PySide6 ^
    -p . ^
    run_screengrab.py

popd
endlocal
