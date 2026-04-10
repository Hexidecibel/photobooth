# Pibooth Feature Analysis

## Overview

pibooth is a Python-based photo booth application for Raspberry Pi with 807 stars, 189 forks, and 151 open issues. Last release was v2.0.8 in July 2023 — the project is effectively in maintenance mode with very slow development. MIT licensed.

## Current Architecture

### Tech Stack
- **UI**: pygame (manual pixel positioning, no widget toolkit)
- **Camera**: picamera (legacy, Pi Camera v1/v2 only), gphoto2 (DSLR), OpenCV (webcam)
- **Printing**: pycups (CUPS integration)
- **GPIO**: gpiozero (buttons + LEDs)
- **Image Processing**: Pillow + optional OpenCV
- **Plugins**: pluggy (same framework as pytest)
- **Config**: INI-based with type coercion
- **Python**: 3.8+ (but classifiers only list 3.8/3.9)

### State Machine
The core is a well-designed pluggy-driven state machine:
```
wait → choose → chosen → preview → capture → processing → print → finish → wait
```
Each state has 4 hooks: `enter`, `do` (loop), `validate` (transition), `exit`. All state logic lives in plugins, not the engine itself. This is the best part of the architecture.

### Camera Abstraction
Auto-detection priority:
1. RPi Camera + gPhoto2 → HybridRpiCamera (Pi preview, DSLR capture)
2. OpenCV + gPhoto2 → HybridCvCamera (webcam preview, DSLR capture)
3. gPhoto2 only → GpCamera
4. RPi Camera only → RpiCamera
5. OpenCV only → CvCamera

Supports image effects via PIL filters (blur, sharpen, contour, emboss, etc.)

### Image Pipeline
1. Camera captures with optional effect
2. Post-process: rotation, crop to aspect ratio, resize, flip
3. Save raw captures to `{savedir}/raw/{date}/`
4. PictureFactory composites final image:
   - Background (solid color or image)
   - Layout matrix (1-4 captures in grid)
   - Overlay PNG composited on top
   - Footer text with {date} and {count} variables
5. Save final composite
6. Optional: generate animation frames for idle display

Default output: 4×6 inches at 600 DPI (2400×3600px)

### GPIO / Hardware
- 2 buttons (capture + print) via gpiozero, BOARD pin numbering
- 2 LEDs with state-dependent blink patterns
- Keyboard fallback (P=capture, Ctrl+E=print, arrows=choose)
- Mouse: left half=capture, right half=print
- Touch: screen-half detection, 4-finger tap=settings menu

### Printer Support
- CUPS integration via pycups
- Event subscription for job status
- Paper formats: 2×6, 3.5×5, 4×6, 5×7, 6×8, 6×9 inches
- Multi-copy tiling on single page
- Max pages limit, max duplicates, auto-print option

### Configuration
INI file at `~/.config/pibooth/pibooth.cfg` with sections:
- **[GENERAL]**: language (14 supported), save directory, autostart, debug, plugin paths
- **[WINDOW]**: size/fullscreen, background color/image, font, text color, arrow style, delays
- **[PICTURE]**: orientation, captures count, effects, cropping, margins, footer text, overlays, backgrounds
- **[CAMERA]**: ISO, flip, rotation, resolution
- **[PRINTER]**: printer name, options dict, delays, auto-print, max pages
- **[CONTROLS]**: debounce, GPIO pin numbers for buttons and LEDs

Plugins can register their own config options.

### Plugin System (40+ hooks)
5 built-in plugins: Camera, Picture, Printer, View, Lights

**Lifecycle hooks**: configure, reset, startup, cleanup
**Setup hooks** (firstresult): setup_camera, setup_picture_factory
**State hooks**: {state}_{enter/do/validate/exit} for all 9 states

Plugins register via setuptools entry points. The 3.x branch (unreleased) adds custom state definitions.

## Official Plugins

| Plugin | Stars | Purpose |
|--------|-------|---------|
| pibooth-picture-template | 29 | XML-based custom picture layouts (diagrams.net) |
| pibooth-qrcode | 11 | QR codes linking to photos |
| pibooth-google-photo | 9 | Upload to Google Photos |
| pibooth-sound-effects | 5 | WAV sound effects per state |
| pibooth-extra-lights | 4 | GPIO LED sequences for startup/preview/flash |
| pibooth-dropbox | 1 | Upload to Dropbox with shareable links |

## Notable Community Plugins

| Plugin | Purpose |
|--------|---------|
| pibooth-picamera2 | Pi Camera v3 / libcamera support (critical for Pi 5) |
| pibooth-lcd-display | I2C/GPIO LCD screen info display |
| pibooth-oled-display | OLED with logos, GIFs, counters |
| pibooth-nextcloud | Self-hosted Nextcloud upload |
| pibooth-s3-upload | AWS S3 upload |
| pibooth-telegram-upload | Send photos via Telegram bot |
| pibooth-serial | Arduino serial trigger |
| pibooth-wifi_manager | WiFi selection on touchscreen |
| pibooth-escpos | Thermal/ESC-POS printer + QR codes |
| pibooth-idle-chats | Audio playback when idle to attract guests |
| pibooth-email | Email sharing |

## Critical Problems

### 1. Raspberry Pi 5 / Modern OS — BROKEN
- `picamera` (legacy) requires `libbcm_host.so` which doesn't exist on Pi 5
- `vcgencmd get_camera` is deprecated on Bookworm/Trixie
- Pi Camera Module v3 not supported
- Issue #290 has 85 comments — the most active issue in the repo
- Community member built working Pi 5 plugin (#651) using rpicam-vid/rpicam-still — maintainers never responded

### 2. Installation — BROKEN on Modern Python
- PEP 668 blocks `sudo pip install` on Bookworm
- Pillow was pinned to 9.2.0 (won't build on Python 3.11+)
- No venv/container story
- `ANTIALIAS` constant and `getsize()` removed in Pillow 10+

### 3. pygame UI — Dated and Fragile
- Manual pixel positioning, no layout engine
- Touch = screen-half detection (not real touch UI)
- No Wayland support
- Crashes: `pygame.error: video system not initialized`
- Single font, single text color, no real theming
- No responsive design, no DPI awareness
- 40 FPS single-threaded event loop

### 4. Camera Integration — Fragile
- gPhoto2 errors produce generic "Oops! Something went wrong" with no diagnostics
- Hybrid mode (preview camera + capture DSLR) has resolution mismatches
- Autofocus failures lock the state machine
- Flash standby crashes the app
- Many DSLR models partially broken (Canon, Sony)

### 5. Project Health — Stalled
- Last release: July 2023 (3 years ago)
- 3.x branch exists but never released
- 151 open issues, many unanswered
- Zero active PRs being reviewed
- Official plugins not updated since 2023
- People submit plugins as issues because there's no contribution path

## Most-Requested Features (Never Implemented)

| Feature | Issues | Comments |
|---------|--------|----------|
| libcamera / picamera2 support | #290, #582, #609, #573, #600, #526, #540, #651 | 85+ |
| Green screen / chromakey | #315, #628, #457 | 15+ |
| GIF / boomerang mode | #632, #488 | 11+ |
| Video capture | #162 | — |
| Post-capture filter selection | #454, #386, #623 | 13+ |
| Better sharing (SMS, QR, cloud) | #429, pibooth_photo_share | — |
| Custom UI templates | #298 | Long-standing |
| Portrait + mixed layouts | #606, #529 | — |
| Neopixel/LED strip integration | #619 | — |
| Form / data collection | #650 | — |
| PIN lock for settings | #641 | — |
| Single-button simplified mode | #449 | — |

## What's Worth Keeping (Concepts, Not Code)

1. **Pluggy-based state machine** — The hook-driven state engine is the best part of pibooth. Port the pattern.
2. **Hybrid camera concept** — Preview from one source, capture from another. Smart pattern for DSLR setups.
3. **Picture factory abstraction** — Background + layout matrix + overlay + text compositing. Good model.
4. **Config import path** — We should support `photobooth import-config ~/.config/pibooth/pibooth.cfg` to migrate existing users' settings.
5. **CUPS printer integration** — The printing model works, just needs better error handling and status reporting.
6. **GPIO button/LED patterns** — The blink patterns for state indication are good UX for physical booths.

## Modernization Recommendations

### UI: FastAPI + Browser Kiosk Mode
- Pi 5 has plenty of RAM/GPU for Chromium kiosk
- CSS theming = unlimited customization for event branding
- Native touch support in browser
- Web backend = built-in remote admin, QR sharing, phone gallery
- Camera preview via MJPEG stream (~60-80ms latency at 720p/15fps, fine for countdown)
- Frontend: Svelte or vanilla JS (keep it light for kiosk)
- Communication: WebSocket for state, MJPEG for preview

### Camera: picamera2 + libcamera First
- Native Pi 5 + Camera Module v3 support
- rpicam-vid for preview streaming, rpicam-still for capture (pattern from #651)
- Keep gPhoto2 for DSLR support
- Keep hybrid pattern (picamera2 preview + DSLR capture)

### New Features to Prioritize
1. Green screen / chromakey (most requested creative feature)
2. GIF / boomerang mode (expected in modern booths)
3. QR code → phone gallery sharing (seamless guest experience)
4. Post-capture effects/filters selection
5. Web-based admin panel for remote configuration
6. Template-based layouts (SVG/HTML, not XML)
7. Video messages

### Infrastructure
- Python 3.11+ only
- Modern dependency management (pyproject.toml, we already have this)
- systemd service for kiosk mode
- Config: TOML + web admin panel
- Plugin system: keep pluggy, expose hooks via FastAPI lifecycle
