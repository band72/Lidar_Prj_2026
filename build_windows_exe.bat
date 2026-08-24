@echo off
setlocal enabledelayedexpansion
title LiDAR Contour Studio - Windows Standalone EXE Builder
echo ==================================================================
echo    LiDAR Contour Studio • Standalone Windows EXE Builder
echo ==================================================================
echo.

:: 1. Check if Python is already available in PATH
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] Python was not found in your system PATH.
    echo [*] Checking standard Windows Python installation locations...

    set "FOUND_PYTHON="
    for %%P in (
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
        "%ProgramFiles%\Python312\python.exe"
        "%ProgramFiles%\Python311\python.exe"
        "%ProgramFiles%\Python310\python.exe"
        "C:\Python312\python.exe"
        "C:\Python311\python.exe"
        "C:\Python310\python.exe"
    ) do (
        if exist "%%~P" (
            set "FOUND_PYTHON=%%~P"
            set "PYTHON_DIR=%%~dpP"
        )
    )

    if defined FOUND_PYTHON (
        echo [*] Found installed Python at: !FOUND_PYTHON!
        echo [*] Adding Python to current session PATH...
        set "PATH=!PYTHON_DIR!;!PYTHON_DIR!Scripts;%PATH%"
    ) else (
        echo.
        echo ==================================================================
        echo  Python is missing. Starting Automated Python 3.11 Download...
        echo ==================================================================
        set "PY_INSTALLER=%TEMP%\python-3.11.9-amd64.exe"
        
        powershell -NoProfile -ExecutionPolicy Bypass -Command ^
            "Write-Host '[*] Downloading official Python 3.11 installer...'; " ^
            "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; " ^
            "(New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe', '$env:TEMP\python-3.11.9-amd64.exe')"

        if not exist "!PY_INSTALLER!" (
            echo [ERROR] Failed to download Python. Please check your internet connection.
            pause
            exit /b 1
        )

        echo [*] Installing Python silently and updating PATH in registry...
        powershell -NoProfile -ExecutionPolicy Bypass -Command ^
            "Start-Process -FilePath '$env:TEMP\python-3.11.9-amd64.exe' -ArgumentList '/quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_pip=1' -Wait"

        del /f /q "!PY_INSTALLER!" >nul 2>&1

        :: Reload PATH from User Registry
        for /f "tokens=2*" %%A in ('reg query HKCU\Environment /v Path 2^>nul') do set "USER_PATH=%%B"
        set "PATH=%USER_PATH%;%PATH%"

        :: Check standard install path again
        if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
            set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
        )
    )
)

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python installation completed but could not be detected.
    echo Please restart this script or restart your PC to refresh environment variables.
    pause
    exit /b 1
)

for /f "tokens=*" %%V in ('python --version 2^>^&1') do echo [*] Active Python: %%V
echo.

:: 2. Create / activate virtual environment
echo [*] Checking / initializing virtual environment...
if not exist "venv" (
    python -m venv venv
)

call venv\Scripts\activate

echo [*] Upgrading packaging tools and dependencies...
python -m pip install --upgrade pip setuptools wheel
pip install pyinstaller pywebview
pip install -e .

echo.
echo [*] Compiling Standalone Windows Executable (.exe)...
pyinstaller --clean --noconfirm LidarContourStudio_win.spec

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] PyInstaller build failed. Check the output above.
    pause
    exit /b %errorlevel%
)

echo.
echo [*] Copying installer helper...
if exist "install_windows.bat" copy "install_windows.bat" "dist\LidarContourStudio\" >nul

echo.
echo ==================================================================
echo  [SUCCESS] Windows Executable built successfully!
echo  Executable Location: dist\LidarContourStudio\LidarContourStudio.exe
echo ==================================================================
echo.
pause
