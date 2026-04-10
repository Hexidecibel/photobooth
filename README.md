# photobooth

**A modern, open-source photo booth for Raspberry Pi.**

Built from scratch with picamera2, FastAPI, and a browser-based UI.

---

## Why This Exists

[pibooth](https://github.com/pibooth/pibooth) paved the way for open-source photo booths. I used it for years and loved it -- 807 stars, great community, solid plugin architecture. It made DIY photo booths a real thing.

But the Pi ecosystem moved on, and pibooth couldn't keep up. The Raspberry Pi 5, Camera Module v3, Bookworm OS, Python 3.11+ -- none of it works with pibooth anymore. [Issue #290](https://github.com/pibooth/pibooth/issues/290) has 85 comments from people who want to use it but can't. The maintainers did incredible work, but the project hasn't had a release in 3 years and the gaps are too wide to patch.

So I built a successor. Not a fork -- a ground-up rewrite that keeps what pibooth got right (pluggy plugins, CUPS printing, GPIO controls, the state machine concept) and rebuilds everything else for 2026.

**Browser UI instead of pygame. picamera2 instead of picamera. FastAPI + WebSocket instead of a 40fps game loop. Works on Pi 4, Pi 5, and your laptop.**

And then I kept going -- animated GIFs with effects inside styled frames, per-shot effect selection, visual template editor, QR sharing over SSH tunnels, and a bunch of features nobody asked for but everyone's going to want.

---

## What Makes This Different

- **Browser-based UI** -- works on any device. iPad, phone, Pi touchscreen, laptop. No pygame, no Wayland crashes, no pixel math.
- **Pi 4 AND Pi 5 with picamera2/libcamera** -- the thing everyone has been asking for. Camera Module v3, full sensor resolution stills, hardware-accelerated crop and zoom.
- **14 photo effects** -- black & white, sepia, vintage, cartoon, watercolor, oil painting, pencil sketch, pop art, and more. OpenCV-powered with PIL fallbacks.
- **Animated GIFs and boomerangs WITH effects** -- effects are applied per-frame. Your cartoon GIF actually looks like a cartoon.
- **Templated GIFs** -- your animated GIF plays INSIDE a styled frame with event branding. Not just raw frames stitched together.
- **Per-shot effect selection** -- each photo in your strip can have a different effect. Photo 1 in black & white, photo 2 in pop art, photo 3 normal. Guests choose.
- **9 built-in layout templates** -- classic strip, polaroid, collage, grid, duo, triple, big-small hero layout. All at 600 DPI, print-ready.
- **Visual drag-and-drop template editor** -- build custom layouts in the admin panel. No JSON editing required (but you can if you want to).
- **Polaroid template with handwritten sharpie font** -- Humor Sans. It looks like someone actually wrote on your polaroid.
- **QR code sharing** -- every photo gets a unique QR code. Guests scan, get their photo on their phone. Done.
- **Built-in SSH tunnel** -- enable `localhost.run` and your QR codes work over cellular. Guests don't need your WiFi. Zero configuration.
- **Green screen / chromakey** -- HSV-based compositing with configurable hue range. Multiple backgrounds, guest picks at capture time.
- **14-language i18n** -- same coverage as pibooth, but actually maintained.
- **Plugin system** -- pluggy-based (same framework as pytest), 15+ hooks covering lifecycle, camera, processing, printing, sharing, and UI. Two registration methods: setuptools entry points or filesystem paths.
- **Email sharing** -- SMTP-based photo delivery with customizable templates.
- **Social sharing** -- Web Share API for native share dialogs on mobile (WhatsApp, Messages, AirDrop, whatever your OS supports).
- **Admin panel** -- live camera framing with zoom/crop/mirror, analytics dashboard, backup/export, template editor, theme editor, branding, sound config, system health.
- **Sound effects** -- countdown beeps, shutter click, applause. Configurable per-event.
- **Slideshow attract mode** -- idle screen cycles through event photos to draw people in.
- **Photo counter persistence** -- session and lifetime counters survive reboots.
- **Auto-recovery watchdog** -- monitors camera and printer, auto-recovers on failure. Idle timeout returns to attract screen.
- **Offline resilience** -- works without internet. Tunnel and sharing degrade gracefully, everything else keeps running.
- **GPIO buttons and LEDs** -- capture and print buttons with state-aware LED patterns (slow blink idle, fast blink capture, solid on review). Graceful fallback on non-Pi hardware.
- **CUPS printer integration** -- auto-print, print limits, multiple copies. Any CUPS-compatible printer.
- **One-command install** -- `sudo deploy/setup.sh` handles system deps, venv, systemd services, optional kiosk mode. Done.
- **Dev workflow** -- `bin/sync --host user@pi --watch` pushes changes to your Pi with hot reload. Edit on your laptop, test on the booth.
- **Pibooth config import** -- upload your `pibooth.cfg` and we convert it. Don't start from scratch.

---

## Screenshots

> TODO: Add screenshots of the booth UI, admin panel, template editor, and gallery.

### Access Points

| URL | What It Does |
|-----|-------------|
| `/booth` | The booth UI -- what your guests see |
| `/admin` | Admin panel -- config, camera, templates, analytics |
| `/gallery` | Event photo gallery |
| `/share/{token}` | Individual photo share page (QR codes point here) |
| `/docs` | API documentation (Swagger) |

---

## Quick Start

### Raspberry Pi (Pi 4 or Pi 5)

```bash
git clone https://github.com/Hexidecibel/photobooth
cd photobooth
sudo deploy/setup.sh
```

That's it. The script installs system dependencies, creates a venv, sets up systemd services, and optionally enables kiosk mode (Chromium fullscreen on boot).

```
Booth:  http://<pi-ip>:8000/booth
Admin:  http://<pi-ip>:8000/admin
```

### For Development

```bash
git clone https://github.com/Hexidecibel/photobooth
cd photobooth
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

No camera required -- it runs gracefully without one. Open `http://localhost:8000/booth`.

### Dev-to-Pi Workflow

```bash
# One-time push
bin/sync --host pi@192.168.1.100

# Auto-sync on every file change
bin/sync --host pi@192.168.1.100 --watch
```

---

## Architecture

**Stack:** FastAPI + WebSocket + vanilla JS (no build step, no npm, no node_modules). picamera2 for camera, OpenCV for effects, Pillow for compositing, pluggy for plugins, SQLite for the gallery, TOML for config.

**145 tests. Zero lint errors.**

```
idle -> choose -> preview -> capture -> processing -> review -> print -> thankyou -> idle
```

Every state transition fires plugin hooks and broadcasts to all connected WebSocket clients. Five built-in plugins handle camera control, image compositing, LED patterns, print jobs, and UI updates.

```
photobooth/
  app/
    main.py                  # FastAPI app, lifespan, route mounting
    camera/                  # picamera2, OpenCV webcam, auto-detection
    processing/              # 14 effects, 9 templates, compositing engine
    services/                # state machine, plugins, sharing, tunnel, watchdog
    plugins/                 # hookspec (15+ hooks), 5 built-in plugins
    routers/                 # booth, admin, camera, gallery, share, printer
    static/                  # HTML, CSS, JS, templates, sounds (no build step)
  deploy/                    # setup.sh, systemd services
  bin/                       # up, down, test, lint, sync, logs, status
  config.toml                # All configuration in one file
```

---

## Coming from pibooth?

Most concepts carry over. Same GPIO pins (different config keys). Same CUPS printers. Same pluggy hooks. We even import your config.

```bash
# Upload your pibooth.cfg via the admin panel, or use the API:
curl -X POST http://localhost:8000/api/admin/config/import \
  -F "file=@~/.config/pibooth/pibooth.cfg"
```

See [docs/MIGRATION.md](docs/MIGRATION.md) for the full migration guide with a config mapping table.

---

## Documentation

| Document | Description |
|----------|-------------|
| [Configuration Reference](docs/CONFIGURATION.md) | Every config option, all 14 sections |
| [Plugin Development](docs/PLUGINS.md) | Hook reference, examples, packaging guide |
| [Template Guide](docs/TEMPLATES.md) | Layout format, built-in templates, building your own |
| [Deployment Guide](docs/DEPLOYMENT.md) | Pi setup, kiosk mode, tunnels, systemd, troubleshooting |
| [Migration from pibooth](docs/MIGRATION.md) | Config mapping, step-by-step migration |

---

## What's Coming

We have a backlog of features we're excited about:

- **AI photo effects** -- style transfer, background removal, face filters using on-device models
- **Video message mode** -- short video clips with countdown
- **Multi-booth management** -- control multiple booths from one admin panel
- **Face detection auto-trigger** -- smile detection, auto-framing
- **Event presets** -- save/load complete event configs (template + theme + branding)
- **Photo approval workflow** -- operator reviews before printing

---

## Contributing

The plugin system means you can extend photobooth without forking it. But if you want to contribute to core:

1. Fork the repo
2. Create a feature branch
3. Make your changes
4. Run `bin/test` and `bin/lint`
5. Open a pull request

Issues and feature requests welcome.

---

pibooth opened the door for me. I built my first photo booth because of it, and it brought a lot of joy to a lot of people. This project exists because of that foundation. If just one person builds a photo booth because of this app, that's a win for me.

---

## License

MIT
