#!/usr/bin/env bash
# Quick launcher for Option 2 Docker Container
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "======================================================="
echo "Starting LiDAR Contour Studio via Docker Container"
echo "======================================================="

docker compose up --build -d

echo ""
echo "[*] Container running at http://localhost:8000"
echo "[*] View logs with: docker compose logs -f"
