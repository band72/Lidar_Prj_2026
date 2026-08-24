# 🐧 LiDAR Contour Studio — Linux Deliverables

This directory contains standalone execution and installation packages for **Linux (Ubuntu, Debian, Fedora, Arch, RHEL)**.

---

### 📦 Files Included

1. **`LidarContourStudio-Linux-x86_64.tar.gz`** (249 MB):
   - Self-contained standalone application bundle with all C++ and Python runtimes included.
2. **`install_linux.sh`**:
   - 1-click installer that installs the app to `~/.local/share/LidarContourStudio/` and adds desktop & application menu shortcuts.
3. **`run_linux.sh`**:
   - Quick launcher script for direct development/local execution.

---

### 🚀 Quick Start Instructions

#### Option A: 1-Click Desktop Icon Installation
```bash
./install_linux.sh
```
*Creates the launcher icon in your Linux Application Menu and on your Desktop.*

#### Option B: Standalone Run (No Install Needed)
```bash
tar -xzf LidarContourStudio-Linux-x86_64.tar.gz
./LidarContourStudio/LidarContourStudio
```
