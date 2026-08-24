#!/usr/bin/env bash
set -e

echo "================================================================="
echo "       LiDAR Contour Studio Engine (Linux Local Worker)"
echo "================================================================="

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 could not be found. Please install Python 3.10+."
    exit 1
fi

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ ! -d "venv" ]; then
    echo "[*] Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
echo "[*] Ensuring dependencies..."
pip install -e . > /dev/null 2>&1

echo "[*] Starting Local LiDAR Processing Engine on http://127.0.0.1:8000"
exec python3 run_server.py
