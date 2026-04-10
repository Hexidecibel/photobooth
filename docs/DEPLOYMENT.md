# Deployment Guide

How to get photobooth running on a Raspberry Pi for an event, set up kiosk mode, configure tunnels for QR sharing, and keep everything running smoothly.

## Table of Contents

- [Hardware Requirements](#hardware-requirements)
- [Raspberry Pi Setup](#raspberry-pi-setup)
- [Installation](#installation)
- [Kiosk Mode](#kiosk-mode)
- [Headless Mode](#headless-mode)
- [Tunnel Setup](#tunnel-setup)
- [systemd Services](#systemd-services)
- [Development Workflow](#development-workflow)
- [Backup and Restore](#backup-and-restore)
- [Troubleshooting](#troubleshooting)

---

## Hardware Requirements

### Minimum

- **Raspberry Pi 5** (4GB or 8GB)
- **Pi Camera Module v3** or USB webcam
- **MicroSD card** (32GB+, A2 rated for speed)
- **Power supply** (USB-C, 5V/5A for Pi 5)
- **Display** -- HDMI monitor, touchscreen, or tablet via headless mode

### Recommended

- **Pi Camera Module v3** -- native libcamera, autofocus, 12MP
- **7" official touchscreen** or HDMI monitor
- **2 arcade buttons** -- capture and print
- **2 LEDs** -- state indicators
- **CUPS-compatible printer** -- Canon SELPHY CP1500, DNP DS-series, or similar dye-sub
- **USB hub** -- if using external printer + keyboard for setup
- **Case/enclosure** -- protect the Pi and mount the camera

### Optional

- **DSLR camera** -- Canon/Nikon/Sony via gphoto2 (for highest image quality)
- **Green screen** -- fabric or collapsible background
- **Ring light** -- for even face lighting
- **WiFi dongle** -- if the built-in WiFi isn't reliable enough for tunnel sharing

---

## Raspberry Pi Setup

### OS Installation

1. Download **Raspberry Pi OS (64-bit, with desktop)** using the [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Flash to your MicroSD card
3. In the imager's settings, set:
   - Username: `pi`
   - WiFi credentials
   - SSH enabled
   - Locale/timezone

### Camera Setup

1. Connect the Pi Camera ribbon cable (power off first)
2. Boot the Pi and verify:

```bash
# Check camera is detected
libcamera-hello --list-cameras

# Test capture
libcamera-still -o test.jpg
```

If using a USB webcam instead:

```bash
# Check the device exists
ls /dev/video*

# Test with OpenCV
python3 -c "import cv2; cap = cv2.VideoCapture(0); print('OK' if cap.isOpened() else 'FAIL')"
```

### Printer Setup

1. Install CUPS: `sudo apt install cups`
2. Add your user to the lpadmin group: `sudo usermod -a -G lpadmin pi`
3. Open CUPS admin: `http://localhost:631`
4. Add your printer and print a test page
5. Note the printer name: `lpstat -a`

---

## Installation

### One-Command Setup

```bash
git clone https://github.com/yourusername/photobooth
cd photobooth
deploy/setup.sh
```

The setup script does the following:

1. **Installs system dependencies:**
   - `python3-venv`, `python3-dev` -- Python build tools
   - `libcamera-dev`, `python3-libcamera`, `python3-picamera2` -- camera support
   - `libcups2-dev` -- printer support
   - `chromium-browser` -- kiosk display
   - `unclutter` -- cursor hiding
   - `fonts-dejavu-core` -- default font

2. **Copies the project** to the install directory (default: `/home/pi/photobooth`)

3. **Creates a Python virtual environment** with `--system-site-packages` (required for picamera2 which is installed system-wide)

4. **Installs the project** and optional dependencies (OpenCV, gpiozero, pycups)

5. **Creates data directories** (`data/photos/`, `data/raw/`)

6. **Installs systemd services** and starts the backend

7. **Optionally enables kiosk mode** (Chromium fullscreen)

### Custom Install Directory

```bash
deploy/setup.sh /opt/photobooth
```

### Manual Installation

If you prefer to do it step by step:

```bash
# System deps
sudo apt install python3-venv python3-dev libcamera-dev python3-libcamera \
    python3-picamera2 libcups2-dev chromium-browser unclutter fonts-dejavu-core

# Clone and setup
git clone https://github.com/yourusername/photobooth
cd photobooth
python3 -m venv .venv --system-site-packages
.venv/bin/pip install -e ".[dev]"
.venv/bin/pip install opencv-python-headless gpiozero pycups qrcode[pil]

# Create dirs
mkdir -p data/photos data/raw

# Start
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Kiosk Mode

Kiosk mode runs Chromium in fullscreen pointing at the booth UI. It's managed by a separate systemd user service.

### Enabling

During `deploy/setup.sh`, you'll be asked if you want to enable kiosk mode. If you said no and want to enable it later:

```bash
mkdir -p ~/.config/systemd/user/
cp deploy/photobooth-kiosk.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable photobooth-kiosk
systemctl --user start photobooth-kiosk
```

### What It Does

The kiosk service (`deploy/photobooth-kiosk.service`):

- Waits for the graphical session to start
- Disables screen blanking and DPMS (display power management)
- Launches Chromium with these flags:
  - `--kiosk` -- fullscreen, no browser chrome
  - `--noerrdialogs` -- suppress error popups
  - `--disable-infobars` -- hide "Chromium is being controlled" bar
  - `--autoplay-policy=no-user-gesture-required` -- allow sound effects
- Points to `http://localhost:8000/booth`
- Auto-restarts if Chromium crashes

### Disabling

```bash
systemctl --user stop photobooth-kiosk
systemctl --user disable photobooth-kiosk
```

### Cursor Hiding

The `unclutter` package hides the mouse cursor after a few seconds of inactivity. The booth UI also sets `hide_cursor = true` in the display config which applies CSS `cursor: none`.

---

## Headless Mode

Run the Pi without a local display and use a tablet (iPad, Android tablet) as the booth screen. The tablet connects over WiFi to the Pi's web server.

### Setup

1. Skip kiosk mode during setup (or disable it)
2. Ensure the Pi and tablet are on the same WiFi network
3. Find the Pi's IP: `hostname -I`
4. On the tablet, open Safari/Chrome and navigate to `http://<pi-ip>:8000/booth`
5. Use the browser's "Add to Home Screen" for a full-screen app experience

### Connection Info

The admin panel at `/admin` shows connection URLs and can generate a QR code for easy tablet setup:

```bash
curl http://localhost:8000/api/admin/connection
```

Returns:
```json
{
    "booth_url": "http://192.168.1.50:8000/booth",
    "admin_url": "http://192.168.1.50:8000/admin",
    "ip": "192.168.1.50",
    "port": 8000
}
```

---

## Tunnel Setup

Tunnels expose the booth to the internet so guests can access shared photos from their phones over cellular data (when they're not on the same WiFi as the booth).

### localhost.run (Recommended)

Zero-install SSH tunnel. No account needed.

```toml
[network]
tunnel_enabled = true
tunnel_provider = "localhost.run"
```

On startup, photobooth opens an SSH tunnel to localhost.run and gets a public URL like `https://abc123.lhr.life`. This URL is automatically used for QR codes and share links.

**Requirements:** SSH client installed (comes with Pi OS). An internet connection.

**Note:** localhost.run URLs are ephemeral -- they change each time the tunnel restarts. That's fine for events (guests scan the QR at the booth, use the link immediately).

### Custom Tunnel

Use ngrok, frp, Cloudflare Tunnel, or any other tunnel provider:

```toml
[network]
tunnel_enabled = true
tunnel_provider = "custom"
tunnel_custom_command = "ngrok http {port}"
tunnel_url_pattern = "https://my-booth.ngrok.io"
```

The `{port}` and `{name}` placeholders in `tunnel_custom_command` are replaced with the server port and tunnel name from config.

### Tunnel Monitoring

The tunnel service automatically monitors the connection and restarts if it drops. Check tunnel status:

```bash
curl http://localhost:8000/api/admin/connection
```

---

## systemd Services

### Backend Service

`deploy/photobooth.service` runs the uvicorn server:

```ini
[Unit]
Description=Photobooth Backend Server
After=network.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/photobooth
Environment=PATH=/home/pi/photobooth/.venv/bin:/usr/bin:/bin
ExecStart=/home/pi/photobooth/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### Common Commands

```bash
# Status
sudo systemctl status photobooth

# Start/stop/restart
sudo systemctl start photobooth
sudo systemctl stop photobooth
sudo systemctl restart photobooth

# View logs
sudo journalctl -u photobooth -f

# View recent logs
sudo journalctl -u photobooth --since "1 hour ago"

# Disable auto-start
sudo systemctl disable photobooth
```

### Kiosk Service

`deploy/photobooth-kiosk.service` runs as a user service (not root):

```bash
# Status
systemctl --user status photobooth-kiosk

# Restart
systemctl --user restart photobooth-kiosk

# Logs
journalctl --user -u photobooth-kiosk -f
```

---

## Development Workflow

### Local Development

On your dev machine (Mac, Linux, Windows):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

The `--reload` flag watches for file changes and restarts automatically. No camera is required -- the server starts gracefully without one.

### Dev-to-Pi Sync

Use `bin/sync` to push code changes from your dev machine to the Pi:

```bash
# One-time sync
bin/sync --host pi@192.168.1.50

# Auto-sync on file changes
bin/sync --host pi@192.168.1.50 --watch
```

`bin/sync` uses rsync and excludes `.venv/`, `__pycache__/`, `.git/`, `data/`, and other non-essential directories.

**Environment variables:**

```bash
export PI_HOST="pi@192.168.1.50"
export PI_DIR="~/photobooth"
bin/sync  # Uses the env vars
```

After syncing, restart the service on the Pi:

```bash
ssh pi@192.168.1.50 "sudo systemctl restart photobooth"
```

### Testing

```bash
bin/test    # Run pytest
bin/lint    # Run ruff
```

### Other bin/ Scripts

| Script | Purpose |
|--------|---------|
| `bin/up` | Start the dev server |
| `bin/down` | Stop services |
| `bin/test` | Run pytest |
| `bin/lint` | Run ruff check |
| `bin/sync` | rsync to Pi |
| `bin/logs` | View service logs |
| `bin/status` | Check service status |

---

## Backup and Restore

### Creating a Backup

**Via admin panel:** Navigate to `/admin` and use the Backup button. Downloads a ZIP containing all photos, raw captures, the gallery database, and counter data.

**Via API:**

```bash
curl -o backup.zip http://localhost:8000/api/admin/backup
```

The backup includes:
- `photos/` -- all composited photos
- `raw/` -- all original captures
- `gallery.db` -- SQLite database with share tokens and metadata
- `counters.json` -- photo/print counter data

### Restoring

Unzip the backup into the `data/` directory:

```bash
unzip backup.zip -d data/
```

---

## Troubleshooting

### Camera not detected

```
WARNING: No camera available: ...
```

**Pi Camera:**
- Check the ribbon cable is seated firmly
- Run `libcamera-hello --list-cameras` to verify the OS sees it
- Ensure `python3-picamera2` is installed: `dpkg -l | grep picamera2`
- On Pi 5, make sure you're using a Camera Module v2 or v3 (v1 may need config changes)

**USB Webcam:**
- Check `/dev/video0` exists: `ls /dev/video*`
- Install OpenCV: `pip install opencv-python-headless`
- Try a different USB port

### GPIO not working

```
WARNING: GPIO not available: ...
```

- Ensure `gpiozero` is installed: `pip install gpiozero`
- Check you're running on a Raspberry Pi (GPIO is disabled on non-Pi hardware)
- Verify pin numbers in `config.toml` match your wiring (BOARD numbering)
- Test buttons directly: `python3 -c "from gpiozero import Button; b = Button(11); b.wait_for_press(); print('OK')"`

### Printer not printing

- Check CUPS: `lpstat -a` should show your printer
- Print a test page via CUPS: `lp -d PrinterName /usr/share/cups/data/testprint`
- Check `printer.printer_name` in config matches the CUPS name exactly
- Check `printer.max_pages` isn't set to 0 (unlimited) when you expect a limit, or a low number that's been reached

### Tunnel not connecting

- Check internet connectivity: `ping google.com`
- For localhost.run: ensure SSH works: `ssh -T nokey@localhost.run`
- Check firewall isn't blocking outbound SSH (port 22)
- Try increasing timeout: the tunnel has a 15-second startup timeout
- Check logs: `sudo journalctl -u photobooth -f | grep -i tunnel`

### Service won't start

```bash
# Check status for error details
sudo systemctl status photobooth

# Check full logs
sudo journalctl -u photobooth --no-pager -n 50
```

Common causes:
- Python venv missing: re-run `deploy/setup.sh`
- Port already in use: `sudo lsof -i :8000`
- Permission issues: check the service runs as the correct user

### High CPU usage

- Check for camera preview issues: if the camera backend is failing, it may retry rapidly
- The watchdog service checks hardware every 10 seconds -- this should be minimal
- Run `htop` to identify the process

### "Video system not initialized" (legacy pibooth error)

This error is from pygame. It doesn't apply to photobooth -- we don't use pygame at all. If you're seeing this, you're still running pibooth. See [MIGRATION.md](MIGRATION.md).
