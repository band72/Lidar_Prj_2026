#!/usr/bin/env python3
"""
Launcher for LiDAR Contour Studio Application Server
Runs on Windows, Linux, and serves Android tablets and mobile devices over local network.
"""

import sys
import os
import uvicorn
import socket

def get_local_ip():
    """Gets local IP address for tablet/mobile device connection."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def main():
    host = "0.0.0.0"
    port = 8000
    local_ip = get_local_ip()

    print("=" * 65)
    print("       LiDAR Contour Studio • Cross-Platform Engine")
    print("=" * 65)
    print(f"[*] Desktop Access (Local):   http://localhost:{port}")
    print(f"[*] Android Tablet / Mobile:  http://{local_ip}:{port}")
    print(f"[*] PWA Installable:          Open in Chrome & 'Add to Home Screen'")
    print("=" * 65)
    print("Starting server... Press Ctrl+C to stop.\n")

    uvicorn.run("app.server.main:app", host=host, port=port, reload=False, log_level="info")

if __name__ == "__main__":
    main()
