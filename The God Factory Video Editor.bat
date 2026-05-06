@echo off
setlocal
title The God Factory Video Editor
cd /d "%~dp0"

if not exist venv\Scripts\activate.bat (
    echo Setup has not been run yet.
    echo Please double-click setup.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
python god_factory_editor\main.py %*
if errorlevel 1 (
    echo.
    echo The app closed with an error.
    echo Check temp\logs\ for details.
    pause
)
