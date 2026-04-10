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

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
INSTALL_DIR="${1:-$PROJECT_DIR}"
CURRENT_USER="${SUDO_USER:-$USER}"
CURRENT_HOME=$(eval echo "~$CURRENT_USER")

echo "Install directory: ${INSTALL_DIR}"
echo "User: ${CURRENT_USER}"
echo ""

# System dependencies
echo "[1/6] Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq \
    python3-venv python3-dev \
    libcamera-dev python3-libcamera python3-picamera2 \
    libcups2-dev \
    unclutter \
    fonts-dejavu-core
# Chromium package name varies by OS version
apt-get install -y -qq chromium 2>/dev/null || apt-get install -y -qq chromium-browser 2>/dev/null || true

# Copy project if installing to a different directory
echo "[2/6] Setting up project..."
if [ "$PROJECT_DIR" != "$INSTALL_DIR" ]; then
    mkdir -p "$INSTALL_DIR"
    rsync -a --exclude '.venv' --exclude 'data' --exclude '.git' \
        "$PROJECT_DIR/" "$INSTALL_DIR/"
    chown -R "$CURRENT_USER:$CURRENT_USER" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# Python venv (run as the actual user, not root)
echo "[3/6] Creating virtual environment..."
sudo -u "$CURRENT_USER" python3 -m venv .venv --system-site-packages
sudo -u "$CURRENT_USER" .venv/bin/pip install --upgrade pip -q
sudo -u "$CURRENT_USER" .venv/bin/pip install -e ".[dev]" -q

# Optional deps
echo "[4/6] Installing optional dependencies..."
sudo -u "$CURRENT_USER" .venv/bin/pip install opencv-python-headless gpiozero pycups qrcode[pil] -q 2>/dev/null || true

# Create data dirs
echo "[5/6] Creating data directories..."
sudo -u "$CURRENT_USER" mkdir -p data/photos data/raw

# Generate and install systemd service (templated for current user/path)
echo "[6/6] Installing systemd services..."
cat > /etc/systemd/system/photobooth.service <<SVCEOF
[Unit]
Description=Photobooth Backend Server
After=network.target

[Service]
Type=simple
User=${CURRENT_USER}
Group=${CURRENT_USER}
WorkingDirectory=${INSTALL_DIR}
Environment=PATH=${INSTALL_DIR}/.venv/bin:/usr/bin:/bin
ExecStart=${INSTALL_DIR}/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable photobooth
systemctl start photobooth

# Kiosk mode (optional)
read -p "Enable kiosk mode (Chromium fullscreen)? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    KIOSK_DIR="${CURRENT_HOME}/.config/systemd/user"
    sudo -u "$CURRENT_USER" mkdir -p "$KIOSK_DIR"

    CHROMIUM_BIN=$(which chromium 2>/dev/null || which chromium-browser 2>/dev/null || echo "/usr/bin/chromium")
    cat > "${KIOSK_DIR}/photobooth-kiosk.service" <<KIOSKEOF
[Unit]
Description=Photobooth Kiosk Display
After=graphical-session.target
Wants=photobooth.service

[Service]
Type=simple
Environment=DISPLAY=:0
ExecStartPre=/bin/sh -c 'xset s off -dpms 2>/dev/null || true'
ExecStart=${CHROMIUM_BIN} --kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble --disable-component-update --check-for-update-interval=31536000 --autoplay-policy=no-user-gesture-required http://localhost:8000/booth
Restart=always
RestartSec=5

[Install]
WantedBy=graphical-session.target
KIOSKEOF
    chown "$CURRENT_USER:$CURRENT_USER" "${KIOSK_DIR}/photobooth-kiosk.service"
    sudo -u "$CURRENT_USER" systemctl --user daemon-reload
    sudo -u "$CURRENT_USER" systemctl --user enable photobooth-kiosk
    echo "Kiosk mode enabled. Will start on next login."
else
    echo "Headless mode. Access booth from any browser on your network."
fi

IP=$(hostname -I | awk '{print $1}')
echo ""
echo "==================================="
echo "  Setup complete!"
echo "==================================="
echo ""
echo "  Server: sudo systemctl status photobooth"
echo "  Logs:   sudo journalctl -u photobooth -f"
echo "  Booth:  http://${IP}:8000/booth"
echo "  Admin:  http://${IP}:8000/admin"
echo ""
