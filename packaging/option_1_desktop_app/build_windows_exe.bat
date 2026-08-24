@echo off
REM Build standalone Windows .exe using PyInstaller
echo =======================================================
echo Building LiDAR Contour Studio Standalone Windows EXE
echo =======================================================

pip install pyinstaller pywebview fastapi uvicorn laspy[lazrs] pyproj shapely numpy scipy jinja2

pyinstaller --noconfirm --onedir --windowed ^
    --name "LidarContourStudio" ^
    --add-data "app\templates;app\templates" ^
    --add-data "app\static;app\static" ^
    packaging\option_1_desktop_app\desktop_launcher.py

echo.
echo Build finished! Executable located in dist\LidarContourStudio\LidarContourStudio.exe
pause
