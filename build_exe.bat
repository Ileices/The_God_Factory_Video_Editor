@echo off
setlocal
title Build Standalone EXE - The God Factory Video Editor
cd /d "%~dp0"

if not exist venv\Scripts\activate.bat (
    echo Run setup.bat first!
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo Installing PyInstaller...
pip install pyinstaller>=6.5 --quiet

echo.
echo Building The God Factory Video Editor.exe...
echo This may take 3-10 minutes.
echo.

pyinstaller ^
    --onefile ^
    --windowed ^
    --name "The God Factory Video Editor" ^
    --icon "resources\icons\app.ico" ^
    --add-data "resources;resources" ^
    --add-data "god_factory_editor;god_factory_editor" ^
    --hidden-import PySide6.QtMultimedia ^
    --hidden-import PySide6.QtMultimediaWidgets ^
    --hidden-import scenedetect ^
    --hidden-import cv2 ^
    --collect-all scenedetect ^
    god_factory_editor\main.py

if errorlevel 1 (
    echo.
    echo Build failed. Check the output above for errors.
    pause
    exit /b 1
)

echo.
echo =============================================
echo  BUILD COMPLETE!
echo =============================================
echo.
echo  Your app is at:
echo    dist\The God Factory Video Editor.exe
echo.
echo  Copy that single .exe file to any Windows PC
echo  and double-click to run — no setup needed.
echo.
pause
