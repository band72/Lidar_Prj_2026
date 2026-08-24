# Option 3: Android Tablet & Mobile Field Setup Guide

This guide walks you through setting up an Android tablet (Samsung Galaxy Tab, Lenovo, Pixel Tablet, etc.) as a field touch controller for LiDAR Contour Studio.

---

## 1. Field Connection Modes

### Mode A: Wi-Fi Hotspot (Recommended for Field / Truck Use)
1. Turn on the **Mobile Hotspot** on your Android tablet or laptop.
2. Connect both devices to the hotspot network.
3. On the laptop/workstation, launch the server:
   ```bash
   python3 run_server.py
   ```
4. Note the printed IP address (e.g. `http://192.168.43.100:8000`).

### Mode B: Local Office / Lab Wi-Fi
1. Ensure the tablet and processing workstation are on the same Wi-Fi router.
2. Launch `python3 run_server.py`.

---

## 2. Installing PWA on Android Tablet

1. Open **Google Chrome** on your Android tablet.
2. Enter `http://<LAPTOP_IP>:8000` into the address bar.
3. Tap the **Three Dots Menu** (top right) &rarr; Select **"Add to Home Screen"** or **"Install Application"**.
4. The **LiDAR Contour Studio** icon will now appear on your tablet home screen and launcher.
5. Tap the icon to launch the app in **immersive, borderless full-screen tablet mode**.

---

## 3. Tablet Touch Capabilities
- **Touch Gesture Zoom & Pan**: Pinch to zoom in/out on high-resolution contours and satellite tiles.
- **Draw Bounding Box with Finger/Stylus**: Tap the *"Draw ROI"* button and drag a rectangle over your survey area.
- **Inspect Elevations**: Tap directly on any contour line to view its elevation value and classification type.
