#!/usr/bin/env bash
set -euo pipefail

echo "==================================="
echo "  Photobooth Setup"
echo "==================================="
echo ""

# Check if running on Pi
if ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "Warning: Not running on a Raspberry Pi."
    echo "Some features (camera, GPIO) may not work."
    echo ""
fi

INSTALL_DIR="${1:-/home/pi/photobooth}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Install directory: ${INSTALL_DIR}"
echo ""

# System dependencies
echo "[1/6] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3-venv python3-dev \
    libcamera-dev python3-libcamera python3-picamera2 \
    libcups2-dev \
    chromium-browser \
    unclutter \
    fonts-dejavu-core

# Copy project
echo "[2/6] Setting up project..."
if [ "$PROJECT_DIR" != "$INSTALL_DIR" ]; then
    mkdir -p "$INSTALL_DIR"
    rsync -a --exclude '.venv' --exclude 'data' --exclude '.git' \
        "$PROJECT_DIR/" "$INSTALL_DIR/"
fi

cd "$INSTALL_DIR"

# Python venv
echo "[3/6] Creating virtual environment..."
python3 -m venv .venv --system-site-packages
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e ".[dev]"

# Optional deps
echo "[4/6] Installing optional dependencies..."
.venv/bin/pip install opencv-python-headless gpiozero pycups qrcode[pil] 2>/dev/null || true

# Create data dirs
echo "[5/6] Creating data directories..."
mkdir -p data/photos data/raw

# Default config
if [ ! -f config.toml ]; then
    cp config.toml.example config.toml 2>/dev/null || true
fi

# Install systemd services
echo "[6/6] Installing systemd services..."
sudo cp deploy/photobooth.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable photobooth
sudo systemctl start photobooth

# Kiosk mode (optional)
read -p "Enable kiosk mode (Chromium fullscreen)? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    mkdir -p ~/.config/systemd/user/
    cp deploy/photobooth-kiosk.service ~/.config/systemd/user/
    systemctl --user daemon-reload
    systemctl --user enable photobooth-kiosk
    echo "Kiosk mode enabled. Will start on next login."
else
    echo "Headless mode. Access booth at http://$(hostname -I | awk '{print $1}'):8000/booth"
fi

echo ""
echo "==================================="
echo "  Setup complete!"
echo "==================================="
echo ""
echo "  Server: sudo systemctl status photobooth"
echo "  Logs:   sudo journalctl -u photobooth -f"
echo "  Booth:  http://$(hostname -I | awk '{print $1}'):8000/booth"
echo ""
