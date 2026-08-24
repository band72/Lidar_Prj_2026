@echo off
title LiDAR Contour Studio - Windows 1-Click Installer
echo ==================================================================
echo    LiDAR Contour Studio • 1-Click Windows Installer
echo ==================================================================
echo.

set SCRIPT_DIR=%~dp0
set VBS_SCRIPT=%TEMP%\CreateShortcut.vbs

echo [*] Creating Desktop Shortcut for LiDAR Contour Studio...

echo Set oWS = WScript.CreateObject("WScript.Shell") > "%VBS_SCRIPT%"
echo sLinkFile = oWS.SpecialFolders("Desktop") ^& "\LiDAR Contour Studio.lnk" >> "%VBS_SCRIPT%"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%VBS_SCRIPT%"

if exist "%SCRIPT_DIR%dist\LidarContourStudio\LidarContourStudio.exe" (
    echo oLink.TargetPath = "%SCRIPT_DIR%dist\LidarContourStudio\LidarContourStudio.exe" >> "%VBS_SCRIPT%"
    echo oLink.WorkingDirectory = "%SCRIPT_DIR%dist\LidarContourStudio" >> "%VBS_SCRIPT%"
) else (
    echo oLink.TargetPath = "%SCRIPT_DIR%run_windows.bat" >> "%VBS_SCRIPT%"
    echo oLink.WorkingDirectory = "%SCRIPT_DIR%" >> "%VBS_SCRIPT%"
)

echo oLink.Description = "LiDAR Contour Studio - Professional Point Cloud Surface Generator" >> "%VBS_SCRIPT%"
echo oLink.Save >> "%VBS_SCRIPT%"

cscript /nologo "%VBS_SCRIPT%"
del "%VBS_SCRIPT%"

echo.
echo ==================================================================
echo  [SUCCESS] Desktop Shortcut created on your Windows Desktop!
echo  Double-click "LiDAR Contour Studio" on your desktop to launch.
echo ==================================================================
echo.
pause
