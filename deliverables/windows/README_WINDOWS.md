# 🪟 LiDAR Contour Studio — Windows Deliverables

This directory contains standalone execution, build, and installation packages for **Windows 10 and Windows 11 (64-bit)**.

---

### 📦 Files Included

1. **`run_windows.bat`**:
   - 1-click launcher with **automated Python detection and silent auto-installation**.
   - If Python is missing, it automatically downloads and installs Python 64-bit and updates your `PATH`.
2. **`install_windows.bat`**:
   - 1-click Windows installer script that automatically creates a desktop shortcut (**`LiDAR Contour Studio.lnk`**) on your Windows Desktop.
3. **`build_windows_exe.bat`**:
   - 1-click compiler that builds the standalone `LidarContourStudio.exe` using PyInstaller.
4. **`LidarContourStudio_win.spec`**:
   - PyInstaller build configuration for Windows environments.

---

### 🚀 Quick Start Instructions

#### Option A: 1-Click Launch
Double-click:
```cmd
run_windows.bat
```
*Automatically starts the LiDAR engine and opens the interface in your browser or desktop window.*

#### Option B: 1-Click Desktop Shortcut
Double-click:
```cmd
install_windows.bat
```
*Creates the "LiDAR Contour Studio" shortcut icon directly on your Windows Desktop.*

#### Option C: Compile Standalone `.exe`
Double-click:
```cmd
build_windows_exe.bat
```
*Produces `dist\LidarContourStudio\LidarContourStudio.exe`.*
