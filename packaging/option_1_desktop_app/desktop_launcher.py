#!/usr/bin/env python3
"""
Option 1: Standalone Desktop Window Launcher for LiDAR Contour Studio
Runs the local backend server in a background thread and presents the user
with a native desktop application window.
"""

import sys
import os
import threading
import time
import socket
import webbrowser
import uvicorn

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port

def start_server_thread(port):
    from app.server.main import app
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

def main():
    port = get_free_port()
    url = f"http://127.0.0.1:{port}"

    # Start FastAPI server in background daemon thread
    server_thread = threading.Thread(target=start_server_thread, args=(port,), daemon=True)
    server_thread.start()

    time.sleep(1.0) # Wait for server to bind

    # Try launching with pywebview if installed, otherwise open native desktop browser
    try:
        import webview
        print(f"[*] Launching LiDAR Contour Studio in native desktop window: {url}")
        webview.create_window(
            title="LiDAR Contour Studio • Professional Edition",
            url=url,
            width=1280,
            height=850,
            min_size=(900, 600)
        )
        webview.start()
    except ImportError:
        print(f"[*] Opening LiDAR Contour Studio in default desktop browser: {url}")
        webbrowser.open(url)
        print("\nApplication is running. Press Ctrl+C in this window to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down LiDAR Contour Studio.")

if __name__ == "__main__":
    main()
