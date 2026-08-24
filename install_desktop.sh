#!/usr/bin/env bash
# LiDAR Contour Studio - 1-Click Linux Desktop Installer
set -e

echo "=================================================================="
echo "    LiDAR Contour Studio • 1-Click Linux Desktop Installer"
echo "=================================================================="

INSTALL_DIR="$HOME/.local/share/LidarContourStudio"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
USER_DESKTOP="$HOME/Desktop"

mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$DESKTOP_DIR"

echo "[*] Installing application files to $INSTALL_DIR..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -d "$SCRIPT_DIR/dist/LidarContourStudio" ]; then
    cp -r "$SCRIPT_DIR/dist/LidarContourStudio/"* "$INSTALL_DIR/"
elif [ -f "$SCRIPT_DIR/LidarContourStudio" ]; then
    cp -r "$SCRIPT_DIR/"* "$INSTALL_DIR/"
else
    echo "[!] dist folder not found, copying project source..."
    cp -r "$SCRIPT_DIR/"* "$INSTALL_DIR/"
fi

# Create symlink in ~/.local/bin
ln -sf "$INSTALL_DIR/LidarContourStudio" "$BIN_DIR/lidar-contour-studio"
chmod +x "$INSTALL_DIR/LidarContourStudio" 2>/dev/null || true

# Generate Desktop Entry
DESKTOP_FILE="$DESKTOP_DIR/lidar-contour-studio.desktop"
cat <<EOF > "$DESKTOP_FILE"
[Desktop Entry]
Version=1.0
Type=Application
Name=LiDAR Contour Studio
GenericName=LiDAR Surface & Contour Engine
Comment=Process LAS/LAZ point clouds into topographic contours, DEM surfaces, DXF, and Shapefiles.
Exec=$INSTALL_DIR/LidarContourStudio
Icon=applications-engineering
Terminal=false
Categories=Science;Geoscience;Engineering;Graphics;
Keywords=lidar;gis;contours;topography;elevation;dem;laz;las;
StartupNotify=true
EOF

chmod +x "$DESKTOP_FILE"

# Copy to user's desktop if Desktop folder exists
if [ -d "$USER_DESKTOP" ]; then
    cp "$DESKTOP_FILE" "$USER_DESKTOP/"
    chmod +x "$USER_DESKTOP/lidar-contour-studio.desktop"
    echo "[*] Desktop shortcut created on your Desktop."
fi

# Update desktop database
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

echo ""
echo "=================================================================="
echo " [SUCCESS] LiDAR Contour Studio is now installed!"
echo " [*] You can launch it from your Linux Application Menu"
echo " [*] Or from your Desktop shortcut"
echo " [*] Or by running: ~/.local/bin/lidar-contour-studio"
echo "=================================================================="
