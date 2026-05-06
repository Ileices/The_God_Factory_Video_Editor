@echo off
setlocal EnableDelayedExpansion
title The God Factory Video Editor - Setup
color 0A

echo.
echo  =========================================================
echo   THE GOD FACTORY VIDEO EDITOR — SETUP
echo  =========================================================
echo.
echo  This will install everything needed to run the app.
echo  You only need to do this ONCE.
echo.
echo  What this does:
echo    1. Checks for Python 3.11+ (downloads if missing)
echo    2. Creates an isolated environment (won't affect your PC)
echo    3. Installs all required libraries
echo    4. Downloads FFmpeg video tools
echo    5. Creates a desktop shortcut for you
echo.
pause

:: ============================================================
:: STEP 1 — CHECK FOR PYTHON
:: ============================================================
echo.
echo [1/5] Checking for Python 3.11+...
echo.

set PYTHON_OK=0
for %%P in (python python3 py) do (
    if !PYTHON_OK!==0 (
        %%P --version >nul 2>&1
        if !errorlevel!==0 (
            for /f "tokens=2" %%V in ('%%P --version 2^>^&1') do (
                for /f "tokens=1,2 delims=." %%A in ("%%V") do (
                    if %%A GEQ 3 (
                        if %%B GEQ 11 (
                            set PYTHON_CMD=%%P
                            set PYTHON_OK=1
                            echo  Found: Python %%V  ^(using %%P^)
                        )
                    )
                )
            )
        )
    )
)

if !PYTHON_OK!==0 (
    echo  Python 3.11 or higher was NOT found on this computer.
    echo.
    echo  Please download Python 3.12 from:
    echo    https://www.python.org/downloads/
    echo.
    echo  During install, CHECK THE BOX: "Add Python to PATH"
    echo.
    echo  After installing Python, run this setup.bat again.
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

:: ============================================================
:: STEP 2 — CREATE VIRTUAL ENVIRONMENT
:: ============================================================
echo.
echo [2/5] Creating isolated Python environment...
echo.

if exist venv (
    echo  Environment already exists. Re-using it.
) else (
    !PYTHON_CMD! -m venv venv
    if !errorlevel! neq 0 (
        echo  ERROR: Could not create Python environment.
        echo  Try running this setup.bat as Administrator.
        pause
        exit /b 1
    )
    echo  Environment created successfully.
)

:: ============================================================
:: STEP 3 — INSTALL PYTHON PACKAGES
:: ============================================================
echo.
echo [3/5] Installing Python libraries (this may take 2-5 minutes)...
echo.

call venv\Scripts\activate.bat

python -m pip install --upgrade pip --quiet
if !errorlevel! neq 0 (
    echo  WARNING: Could not upgrade pip. Continuing anyway...
)

pip install -r requirements.txt
if !errorlevel! neq 0 (
    echo.
    echo  ERROR: Some packages failed to install.
    echo  Check your internet connection and try again.
    echo.
    pause
    exit /b 1
)

echo.
echo  All Python libraries installed successfully!

:: ============================================================
:: STEP 4 — DOWNLOAD FFMPEG
:: ============================================================
echo.
echo [4/5] Downloading FFmpeg video tools...
echo.

if exist resources\ffmpeg\ffmpeg.exe (
    echo  FFmpeg already downloaded. Skipping.
    goto :ffmpeg_done
)

mkdir resources\ffmpeg 2>nul

:: Use PowerShell to download FFmpeg (built into Windows 10/11)
echo  Downloading FFmpeg from github.com (about 80 MB)...
powershell -Command ^
    "$url = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip';" ^
    "$zip = 'resources\ffmpeg\ffmpeg.zip';" ^
    "Write-Host '  Downloading...' -NoNewline;" ^
    "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;" ^
    "Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing;" ^
    "Write-Host ' Done!'"

if !errorlevel! neq 0 (
    echo.
    echo  Could not automatically download FFmpeg.
    echo  Please manually download it from: https://ffmpeg.org/download.html
    echo  Extract ffmpeg.exe and ffprobe.exe to: resources\ffmpeg\
    echo.
    echo  The app will still work after you do this.
    goto :ffmpeg_done
)

echo  Extracting FFmpeg...
powershell -Command ^
    "Add-Type -AssemblyName System.IO.Compression.FileSystem;" ^
    "$zip = 'resources\ffmpeg\ffmpeg.zip';" ^
    "$dest = 'resources\ffmpeg\extracted';" ^
    "[IO.Compression.ZipFile]::ExtractToDirectory($zip, $dest);" ^
    "$bin = Get-ChildItem $dest -Recurse -Filter 'ffmpeg.exe' | Select-Object -First 1;" ^
    "Copy-Item $bin.FullName 'resources\ffmpeg\ffmpeg.exe';" ^
    "$probe = Get-ChildItem $dest -Recurse -Filter 'ffprobe.exe' | Select-Object -First 1;" ^
    "Copy-Item $probe.FullName 'resources\ffmpeg\ffprobe.exe';" ^
    "Remove-Item $zip -Force;" ^
    "Remove-Item $dest -Recurse -Force;" ^
    "Write-Host '  FFmpeg extracted successfully!'"

:ffmpeg_done

:: ============================================================
:: STEP 5 — CREATE DESKTOP SHORTCUT
:: ============================================================
echo.
echo [5/5] Creating desktop shortcut...
echo.

set APP_DIR=%~dp0
set SHORTCUT_VBS=%APP_DIR%make_shortcut.vbs

echo Set oWS = WScript.CreateObject("WScript.Shell") > "%SHORTCUT_VBS%"
echo sLinkFile = oWS.SpecialFolders("Desktop") ^& "\The God Factory Video Editor.lnk" >> "%SHORTCUT_VBS%"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%SHORTCUT_VBS%"
echo oLink.TargetPath = "%APP_DIR%The God Factory Video Editor.bat" >> "%SHORTCUT_VBS%"
echo oLink.WorkingDirectory = "%APP_DIR%" >> "%SHORTCUT_VBS%"
echo oLink.Description = "The God Factory Video Editor" >> "%SHORTCUT_VBS%"
echo oLink.Save >> "%SHORTCUT_VBS%"

cscript //nologo "%SHORTCUT_VBS%"
if !errorlevel!==0 (
    echo  Desktop shortcut created!
) else (
    echo  Could not create shortcut ^(may need Administrator^). 
    echo  You can still launch the app by double-clicking:
    echo    "The God Factory Video Editor.bat"
)

:: ============================================================
:: DONE
:: ============================================================
echo.
echo  =========================================================
echo   SETUP COMPLETE!
echo  =========================================================
echo.
echo  To start editing:
echo    - Double-click "The God Factory Video Editor" on your Desktop
echo    - OR double-click "The God Factory Video Editor.bat" here
echo.
echo  First time? The app will guide you through your first clip.
echo.
echo  Press any key to launch the app now...
pause >nul

call "The God Factory Video Editor.bat"
