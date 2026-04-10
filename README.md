# photobooth

**A modern, open-source photo booth for Raspberry Pi 5.**

Built from the ground up with picamera2, FastAPI, and a browser-based UI -- because your photo booth shouldn't be stuck in 2020.

- **Pi 5 native** -- picamera2/libcamera, no legacy hacks
- **Web-based UI** -- touch-optimized kiosk in Chromium, CSS theming, 14 languages
- **9 built-in effects** -- black & white, sepia, vintage, warm, cool, blur, sharpen, high contrast
- **9 layout templates** -- classic strip, polaroid, collage, grid, and more
- **Green screen** -- real-time chromakey compositing
- **GIF and boomerang** -- animated capture modes
- **QR sharing** -- guests scan and download instantly
- **CUPS printing** -- auto-print, print limits, any CUPS-compatible printer
- **Admin panel** -- web-based config editor, analytics, camera framing, backup/export
- **GPIO buttons and LEDs** -- state-aware hardware controls with graceful fallback
- **Plugin system** -- pluggy-based, 15+ hooks, extend anything
- **One-command deploy** -- `deploy/setup.sh` handles everything

---

## Table of Contents

- [The Story](#the-story)
- [Features](#features)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Coming from pibooth?](#coming-from-pibooth)
- [Architecture](#architecture)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

---

## The Story

[pibooth](https://github.com/pibooth/pibooth) is the most popular open-source photo booth software, with 807 stars and a solid plugin ecosystem. But it's effectively dead.

**The problems:**

- **Broken on Pi 5.** It depends on the legacy `picamera` library, which requires `libbcm_host.so` -- a library that doesn't exist on Raspberry Pi 5. The Camera Module v3 isn't supported at all. Issue #290 has 85 comments from people asking for Pi 5 support. A community member even built a working plugin (#651) -- the maintainers never responded.

- **Won't install on modern Python.** Pillow was pinned to 9.2.0, which won't build on Python 3.11+. PEP 668 blocks `sudo pip install` on Bookworm. There's no venv or container story.

- **Dated UI.** The pygame-based interface uses manual pixel positioning, has no real touch support (it detects which half of the screen you tapped), no Wayland support, and crashes with `pygame.error: video system not initialized`. Single font, single text color, no theming.

- **151 open issues, no releases in 3 years.** The 3.x branch exists but was never released. Zero active PRs being reviewed. People submit plugins as issues because there's no contribution path.

**The most-requested features** -- green screen, GIF mode, post-capture filter selection, better sharing, custom UI templates -- were never implemented.

We built the replacement. Same plugin-driven architecture (pluggy), same camera concepts (hybrid DSLR mode), same CUPS printing -- but on a modern stack that actually works on current hardware.

---

## Features

### Camera

- **picamera2 / libcamera** -- native Pi 5 and Camera Module v3 support
- **OpenCV webcam** -- any USB webcam via OpenCV
- **gphoto2 DSLR** -- Canon, Nikon, Sony (planned)
- **Hybrid mode** -- Pi camera for live preview, DSLR for high-res capture
- **Digital zoom and crop** -- fractional crop region (0.0-1.0)
- **Mirror controls** -- independent mirror for preview vs. capture
- **Auto-detection** -- picks the best available backend automatically

### User Interface

- **Browser-based kiosk** -- Chromium in fullscreen, no pygame
- **Touch-optimized** -- real touch events, not screen-half detection
- **CSS theming** -- full control via CSS variables, upload custom themes from admin panel
- **14 languages** -- same language set as pibooth
- **Responsive** -- works on Pi's HDMI display, tablets, phones
- **Idle timeout** -- returns to attract screen after configurable inactivity

### Photo Modes

- **Single shot** -- one photo, one print
- **Multi-shot** -- 2, 3, or 4 captures composed into a layout
- **GIF** -- rapid sequence capture, animated output
- **Boomerang** -- forward-reverse loop animation

### Effects and Filters

9 built-in PIL-based effects applied at capture time:

| Effect | Description |
|--------|-------------|
| `none` | Original photo |
| `bw` | Black and white |
| `sepia` | Warm brown tones |
| `vintage` | Desaturated, warm tint, reduced contrast |
| `warm` | Boosted reds, reduced blues |
| `cool` | Boosted blues, reduced reds |
| `blur` | Gaussian blur |
| `sharpen` | Sharpening filter |
| `high_contrast` | 1.5x contrast boost |

### Green Screen (Chromakey)

- HSV-based chroma key compositing
- Configurable hue center and range
- Multiple background images
- Guest picks background at capture time

### Templates and Layouts

9 built-in print layouts, all at 600 DPI:

| Template | Size | Slots | Description |
|----------|------|-------|-------------|
| `classic-4x6` | 4x6" | 4 | Traditional photo strip (4 horizontal rows) |
| `strip-2x6` | 2x6" | 4 | Narrow strip format |
| `single` | 4x6" | 1 | Single large photo |
| `polaroid-4x6` | 4x6" | 1 | Polaroid-style with large footer |
| `duo-4x6` | 4x6" | 2 | Two side-by-side portraits |
| `triple-4x6` | 4x6" | 3 | Three horizontal rows |
| `collage-4x6` | 4x6" | 4 | Scattered layout with rotation |
| `grid-2x2-4x6` | 4x6" | 4 | 2x2 grid on dark background |
| `big-small-4x6` | 4x6" | 3 | One large hero + two small |

Templates use a JSON format with fractional coordinates (0.0-1.0). Create new ones with the visual editor in the admin panel, or write JSON by hand. See [docs/TEMPLATES.md](docs/TEMPLATES.md).

Guests can pick their own template at the choose screen when `guest_picks_template` is enabled.

### Printing

- **CUPS integration** -- works with any CUPS-compatible printer
- **Auto-print** -- print immediately after capture (no button needed)
- **Print limits** -- `max_pages` to control paper usage
- **Multiple copies** -- configurable copies per print job
- **State-aware** -- print button LED lights up when printing is available

### Sharing

- **QR codes** -- generated per photo, guests scan to download
- **Share URLs** -- unique token-based links (`/share/{token}`)
- **Web Share API** -- native share dialog on mobile (WhatsApp, Messages, etc.)
- **Email** -- SMTP-based photo delivery with customizable templates
- **Gallery** -- web-based gallery at `/gallery` showing all event photos

### Hardware (GPIO)

- **2 buttons** -- capture and print, via gpiozero (BOARD pin numbering)
- **2 LEDs** -- state-dependent blink patterns:
  - Idle: capture LED slow blink (1s on/off)
  - Choose: both LEDs blink (0.5s)
  - Preview: capture LED solid on
  - Capture: capture LED fast blink (0.1s)
  - Processing: both LEDs medium blink (0.3s)
  - Review: both LEDs solid on
  - Print: print LED solid on
- **Graceful fallback** -- runs without GPIO on non-Pi hardware (dev machines, laptops)
- **Keyboard fallback** -- works via WebSocket events from the browser

### Admin Panel

Access at `/admin`:

- **Config editor** -- edit all settings, saves to `config.toml`
- **Camera framing** -- live preview with zoom/crop/mirror controls
- **Template editor** -- visual drag-and-drop layout builder
- **Analytics** -- photos per hour, counters, uptime
- **System info** -- disk, memory, camera, printer, GPIO status
- **Backup/export** -- download ZIP of all photos + gallery database
- **Branding** -- upload logo, set company name and tagline
- **Theme editor** -- CSS variable customization
- **Sound config** -- configure sound effects for each event
- **Connection info** -- IP addresses, URLs, QR for tablet connection

### Branding

- **Logo upload** -- PNG/SVG via admin panel, positioned top/bottom/overlay
- **Company name and tagline** -- displayed on idle screen and prints
- **CSS theming** -- override any visual element
- **Footer text** -- customizable with `{event_name}`, `{date}`, `{count}` variables

### Networking

- **Built-in tunnel** -- localhost.run (zero-dependency SSH tunnel) for QR sharing over cellular
- **Custom tunnel support** -- plug in ngrok, frp, or self-hosted tunnels
- **Headless mode** -- no local display, use iPad/tablet as booth screen
- **Hotspot** -- built-in WiFi hotspot for offline events (planned)
- **Auto-restart** -- tunnel monitor detects disconnects and reconnects

### Operations

- **Watchdog service** -- monitors camera and printer, auto-recovers on failure
- **Idle timeout** -- configurable return to attract screen
- **systemd services** -- `photobooth.service` (backend) + `photobooth-kiosk.service` (display)
- **Offline resilience** -- works without internet (tunnel/sharing degrade gracefully)
- **Counter service** -- tracks photos taken, pages printed, session and lifetime totals

### Plugin System

Built on [pluggy](https://pluggy.readthedocs.io/) (the same framework as pytest):

- **15+ hooks** -- lifecycle, state machine, camera, processing, printing, sharing, UI
- **5 built-in plugins** -- Camera, Picture, Printer, View, Lights
- **Two registration methods** -- setuptools entry points or filesystem paths
- **Custom config** -- plugins can register their own configuration options
- **Custom routes** -- plugins can add API endpoints via `register_routes`

See [docs/PLUGINS.md](docs/PLUGINS.md) for the full plugin development guide.

### Deployment

- **One-command setup** -- `deploy/setup.sh` installs deps, creates venv, sets up systemd
- **Kiosk mode** -- optional Chromium fullscreen on boot
- **bin/sync** -- rsync project from dev machine to Pi, with `--watch` for auto-sync
- **Development mode** -- `uvicorn app.main:app --reload` with hot reload

---

## Quick Start

### On Raspberry Pi 5

```bash
git clone https://github.com/yourusername/photobooth
cd photobooth
deploy/setup.sh
```

The setup script will:
1. Install system dependencies (libcamera, picamera2, CUPS, Chromium)
2. Create a Python virtual environment with `--system-site-packages`
3. Install the project and optional deps (OpenCV, gpiozero, pycups)
4. Create data directories
5. Install and start the systemd service
6. Optionally enable kiosk mode (Chromium fullscreen on boot)

### For Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

The server starts at `http://localhost:8000`. No camera required -- it runs gracefully without one.

### Dev-to-Pi Workflow

```bash
# One-time sync
bin/sync --host pi@192.168.1.100

# Auto-sync on file changes
bin/sync --host pi@192.168.1.100 --watch
```

---

## Usage

### Access Points

| URL | Purpose |
|-----|---------|
| `http://<pi-ip>:8000/booth` | Booth UI (what guests see) |
| `http://<pi-ip>:8000/admin` | Admin panel |
| `http://<pi-ip>:8000/gallery` | Event photo gallery |
| `http://<pi-ip>:8000/docs` | API documentation (Swagger) |
| `http://<pi-ip>:8000/health` | Health check endpoint |

### Configuration

All settings live in `config.toml` at the project root. Edit it directly or use the admin panel at `/admin`.

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for the full reference.

### GPIO Wiring

Default pin assignments (BOARD numbering):

```
Raspberry Pi GPIO Header
========================

Pin 7  ---- Print Button
Pin 11 ---- Capture Button
Pin 13 ---- Print LED (+ resistor)
Pin 15 ---- Capture LED (+ resistor)
GND    ---- Common ground for buttons and LEDs
```

Buttons connect between the GPIO pin and ground (internal pull-up). LEDs need a current-limiting resistor (220-330 ohm).

Change pin assignments in `config.toml` under `[controls]` or via the admin panel.

---

## Coming from pibooth?

If you're migrating from pibooth, most concepts carry over directly:

- Same GPIO pins (just different config key names)
- Same cameras (gphoto2 DSLRs, CUPS printers)
- Same plugin architecture (pluggy hooks)
- Config import tool reads your `pibooth.cfg` and converts it

```bash
# Upload your pibooth.cfg via the admin panel
# Or use the API directly:
curl -X POST http://localhost:8000/api/admin/config/import \
  -F "file=@~/.config/pibooth/pibooth.cfg"
```

See [docs/MIGRATION.md](docs/MIGRATION.md) for the full migration guide with a config mapping table.

---

## Architecture

```
photobooth/
  app/
    main.py              # FastAPI app, lifespan, route mounting
    config.py            # TOML config loader
    models/
      config_schema.py   # Pydantic config models (14 sections)
      state.py           # BoothState enum, transitions, CaptureSession
    camera/
      base.py            # Abstract camera interface
      factory.py         # Auto-detection factory
      picamera2.py       # Pi Camera backend (libcamera)
      webcam.py          # OpenCV webcam backend
    hardware/
      gpio.py            # GPIO buttons + LEDs (gpiozero)
      factory.py         # Hardware setup factory
      printer.py         # CUPS printer integration
    processing/
      effects.py         # PIL image effects (9 filters)
      templates.py       # JSON layout template loader
      composer.py        # Photo compositing engine
    services/
      state_machine.py   # Hook-driven state machine
      plugin_manager.py  # Pluggy plugin loading
      share_service.py   # SQLite gallery + QR codes
      tunnel_service.py  # SSH tunnel (localhost.run / custom)
      watchdog.py        # Hardware health monitor
      counter_service.py # Photo/print counters
      email_service.py   # SMTP email sharing
      config_service.py  # Pibooth config importer
    plugins/
      hookspec.py        # All hook definitions
      builtin/           # 5 built-in plugins
    routers/
      booth.py           # WebSocket + booth UI endpoints
      admin.py           # Admin panel API
      camera.py          # MJPEG stream + capture
      gallery.py         # Photo gallery
      share.py           # QR share endpoints
      printer.py         # Print endpoints
      api.py             # General API
    static/              # HTML, CSS, JS, templates, sounds
  deploy/
    setup.sh             # One-command Pi setup
    photobooth.service   # systemd backend service
    photobooth-kiosk.service  # systemd kiosk display
  bin/
    up                   # Start dev server
    down                 # Stop services
    test                 # Run pytest
    lint                 # Run ruff
    sync                 # rsync to Pi
    logs                 # View logs
    status               # Service status
  config.toml            # Configuration file
  pyproject.toml         # Python project metadata
```

**Stack:** Python 3.11+, FastAPI, uvicorn, Pydantic, pluggy, Pillow, SQLite, picamera2, gpiozero, pycups.

**State machine flow:**

```
idle -> choose -> preview -> capture -> processing -> review -> print -> thankyou -> idle
                                                   |-> thankyou (skip print)
```

Each state transition fires `state_exit` and `state_enter` hooks, and broadcasts the change to all connected WebSocket clients. The 5 built-in plugins handle camera control, image compositing, LED patterns, print jobs, and UI updates.

---

## Documentation

| Document | Description |
|----------|-------------|
| [Configuration Reference](docs/CONFIGURATION.md) | Every config option documented |
| [Plugin Development](docs/PLUGINS.md) | Hook reference, examples, packaging |
| [Template Guide](docs/TEMPLATES.md) | Layout format, built-in templates, creating your own |
| [Migration from pibooth](docs/MIGRATION.md) | Config mapping, step-by-step migration |
| [Deployment Guide](docs/DEPLOYMENT.md) | Pi setup, kiosk mode, tunnels, systemd, troubleshooting |

---

## Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-thing`)
3. Make your changes
4. Run tests and linting:
   ```bash
   bin/test
   bin/lint
   ```
5. Commit and push
6. Open a pull request

**Code style:** Python, ruff for linting/formatting, line length 88, functional patterns preferred.

---

## License

MIT
