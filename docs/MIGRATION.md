# Migrating from pibooth

This guide walks you through converting an existing pibooth installation to photobooth. The transition is straightforward -- most concepts map directly, and there's a config import tool that handles the heavy lifting.

## Table of Contents

- [Why Migrate](#why-migrate)
- [What Carries Over](#what-carries-over)
- [What Changes](#what-changes)
- [Auto-Import Your Config](#auto-import-your-config)
- [Config Mapping Table](#config-mapping-table)
- [Plugin Migration](#plugin-migration)
- [GPIO](#gpio)
- [Hardware Compatibility](#hardware-compatibility)
- [Step-by-Step Walkthrough](#step-by-step-walkthrough)

---

## Why Migrate

- **Pi 5 support.** pibooth depends on the legacy `picamera` library which requires `libbcm_host.so` -- this doesn't exist on Raspberry Pi 5. photobooth uses `picamera2` with native libcamera support.
- **Modern Python.** pibooth pins Pillow to 9.2.0 (won't build on Python 3.11+) and has no PEP 668 / venv story. photobooth requires Python 3.11+ and modern Pillow 10.4+.
- **Web-based UI.** No more pygame. The browser-based UI supports real touch input, CSS theming, responsive design, and works on Wayland.
- **Active development.** pibooth has 151 open issues and no releases since July 2023.
- **Features.** Green screen, GIF/boomerang, QR sharing, admin panel, template editor, email sharing -- all the most-requested features that were never implemented in pibooth.

---

## What Carries Over

These concepts work the same way (or very similarly):

- **GPIO buttons and LEDs** -- same gpiozero library, same wiring, just different config key names
- **CUPS printing** -- same pycups integration, same printer setup
- **gphoto2 DSLRs** -- same camera support (planned for Phase 2)
- **Plugin architecture** -- same pluggy framework, similar hook patterns
- **Image effects** -- same PIL-based filters (plus more)
- **Footer text variables** -- `{date}` and `{count}` still work, plus `{event_name}`
- **Photo compositing** -- same concept: background + photo slots + overlay + footer

---

## What Changes

| pibooth | photobooth | Notes |
|---------|------------|-------|
| pygame UI | Browser/Chromium kiosk | Touch, CSS themes, responsive |
| picamera (legacy) | picamera2/libcamera | Pi 5 + Camera Module v3 |
| INI config (`pibooth.cfg`) | TOML config (`config.toml`) | Cleaner syntax, validated with Pydantic |
| `~/.config/pibooth/pibooth.cfg` | `./config.toml` (project root) | Config lives with the project |
| State: `wait` | State: `idle` | Same concept, different name |
| State: `chosen` | (merged into `choose`) | Simplified flow |
| State: `finish` | State: `thankyou` | Same concept |
| `picture_btn_pin` | `capture_button_pin` | Renamed for clarity |
| `picture_led_pin` | `capture_led_pin` | Renamed for clarity |
| `print_btn_pin` | `print_button_pin` | Renamed for clarity |
| `print_led_pin` | `print_led_pin` | Same name |
| `max_duplicates` | `copies` | Renamed |
| `debounce_delay` (seconds) | `debounce_ms` (milliseconds) | Unit change |
| XML templates (diagrams.net) | JSON templates | Simpler, visual editor in admin |
| Setuptools-only plugins | Setuptools + filesystem paths | Easier local development |
| `sudo pip install` | `pip install -e "."` in venv | Proper Python packaging |

**State machine comparison:**

```
pibooth:     wait -> choose -> chosen -> preview -> capture -> processing -> print -> finish -> wait
photobooth:  idle -> choose -> preview -> capture -> processing -> review -> print -> thankyou -> idle
```

---

## Auto-Import Your Config

photobooth includes a config import tool that reads your `pibooth.cfg` and converts it to our `config.toml` format.

### Via the Admin Panel

1. Start photobooth: `bin/up` (or `deploy/setup.sh` on the Pi)
2. Open the admin panel: `http://<pi-ip>:8000/admin`
3. Navigate to Configuration > Import
4. Upload your `pibooth.cfg` file (usually at `~/.config/pibooth/pibooth.cfg`)
5. Review the converted settings and warnings
6. Apply

### Via the API

```bash
curl -X POST http://localhost:8000/api/admin/config/import \
  -F "file=@~/.config/pibooth/pibooth.cfg"
```

The response includes the converted config and a list of warnings for dropped options.

### What Gets Imported

The import tool maps these pibooth sections:

- `[GENERAL]` language, directory, debug
- `[CAMERA]` flip, rotation, resolution
- `[PICTURE]` orientation, captures, footer text, overlays, backgrounds
- `[PRINTER]` printer name, auto-print, max pages, max duplicates
- `[CONTROLS]` all GPIO pin numbers, debounce delay
- `[WINDOW]` size/fullscreen

### What Gets Dropped

These pibooth options have no equivalent (the functionality is handled differently or doesn't apply):

- `[WINDOW]` font, text_color, arrows, animate -- CSS handles all theming now
- `[PICTURE]` captures_effects, captures_cropping, margin_thick -- templates handle layout
- `[CAMERA]` iso, delete_internal_memory -- picamera2 handles these differently
- `[GENERAL]` vkeyboard, plugins, plugins_disabled -- different plugin loading mechanism

---

## Config Mapping Table

### [GENERAL]

| pibooth Key | photobooth Key | Notes |
|-------------|----------------|-------|
| `language` | `general.language` | Same values (en, fr, de, etc.) |
| `directory` | `general.save_dir` | Default changed from `~/.pibooth` to `data` |
| `debug` | `general.debug` | Same |
| `autostart` | `general.autostart_delay` | Was bool, now int (seconds) |
| `vkeyboard` | -- | Dropped (browser has native keyboard) |
| `plugins` | `plugin.paths` | Now a list of file paths |
| `plugins_disabled` | -- | Dropped (use `plugin.enabled` allowlist) |

### [CAMERA]

| pibooth Key | photobooth Key | Notes |
|-------------|----------------|-------|
| `flip` | `camera.flip_horizontal` | Same |
| `rotation` | `camera.rotation` | Same |
| `resolution` | `camera.still_resolution` | Was tuple string, now array |
| `iso` | -- | Dropped (picamera2 auto-exposure) |
| `delete_internal_memory` | -- | Dropped |

### [PICTURE]

| pibooth Key | photobooth Key | Notes |
|-------------|----------------|-------|
| `orientation` | `picture.orientation` | Same |
| `captures` | `picture.capture_count` | Was tuple like `(4, 1)`, now single int |
| `footer_text1` | `picture.footer_text` | Supports `{event_name}`, `{date}`, `{count}` |
| `footer_text2` | -- | Use `{date}` variable in footer_text |
| `overlays` | `picture.overlay_path` | Single path instead of tuple |
| `backgrounds` | `picture.background_color` / `picture.background_image` | Split into color and image |
| `captures_effects` | `picture.default_effect` | Single default + guest picker |
| `captures_cropping` | -- | Dropped (templates handle layout) |
| `margin_thick` | -- | Dropped (templates handle spacing) |

### [PRINTER]

| pibooth Key | photobooth Key | Notes |
|-------------|----------------|-------|
| `printer_name` | `printer.printer_name` | Same |
| `auto_print` | `printer.auto_print` | Same |
| `max_pages` | `printer.max_pages` | Same |
| `max_duplicates` | `printer.copies` | Renamed |
| `printer_delay` | -- | Dropped (handled by CUPS) |
| `pictures_per_page` | -- | Dropped (templates handle tiling) |

### [CONTROLS]

| pibooth Key | photobooth Key | Notes |
|-------------|----------------|-------|
| `picture_btn_pin` | `controls.capture_button_pin` | Renamed |
| `picture_led_pin` | `controls.capture_led_pin` | Renamed |
| `print_btn_pin` | `controls.print_button_pin` | Renamed |
| `print_led_pin` | `controls.print_led_pin` | Same name |
| `debounce_delay` | `controls.debounce_ms` | Seconds -> milliseconds |

### [WINDOW]

| pibooth Key | photobooth Key | Notes |
|-------------|----------------|-------|
| `size` (fullscreen) | `display.fullscreen = true` | Mapped |
| `size` (WxH) | `display.width` / `display.height` | Mapped |
| `background` | -- | Dropped (CSS theming) |
| `font` | -- | Dropped (CSS theming) |
| `text_color` | -- | Dropped (CSS theming) |
| `arrows` | -- | Dropped (CSS theming) |
| `animate` | -- | Dropped |
| `flash` | -- | Dropped |

---

## Plugin Migration

### Hook Mapping

pibooth and photobooth both use pluggy, so the patterns are similar. Here's how the hooks map:

| pibooth Hook | photobooth Hook | Notes |
|--------------|-----------------|-------|
| `pibooth_configure` | `booth_configure` | Same pattern |
| `pibooth_reset` | -- | No equivalent (browser handles UI reset) |
| `pibooth_startup` | `booth_startup` | Same pattern |
| `pibooth_cleanup` | `booth_cleanup` | Same pattern |
| `pibooth_setup_camera` | `setup_camera` | Same pattern (firstresult) |
| `pibooth_setup_picture_factory` | -- | Templates replace the picture factory |
| `state_wait_enter` | `state_enter(state="idle")` | Unified hook with state parameter |
| `state_wait_do` | `state_do(state="idle")` | Unified hook with state parameter |
| `state_wait_validate` | -- | Transitions are explicit, no validation hook |
| `state_wait_exit` | `state_exit(state="idle")` | Unified hook with state parameter |
| (same pattern for all states) | | |

### Key Differences

1. **Unified state hooks.** pibooth has separate hooks per state (e.g., `state_wait_enter`, `state_capture_enter`). photobooth uses a single `state_enter` hook with a `state` parameter. Filter on the state name in your implementation.

2. **Async support.** photobooth hooks can be async. The plugin manager runs sync hooks in a thread executor automatically.

3. **New hooks.** photobooth adds `pre_capture`, `post_capture`, `process_capture`, `post_compose`, `pre_print`, `post_print`, `on_share`, and `register_routes` -- none of which exist in pibooth.

### Migration Example

**pibooth plugin:**
```python
import pibooth

@pibooth.hookimpl
def state_capture_enter(cfg, app, win):
    app.camera.flash(True)

@pibooth.hookimpl
def state_capture_exit(cfg, app, win):
    app.camera.flash(False)
```

**photobooth plugin:**
```python
from app.plugins.hookspec import hookimpl

class MyPlugin:
    @hookimpl
    def state_enter(self, state: str, session):
        if state == "capture":
            self.flash.on()

    @hookimpl
    def state_exit(self, state: str, session):
        if state == "capture":
            self.flash.off()
```

---

## GPIO

Your existing wiring works with photobooth. Just update the config key names:

| pibooth Config | photobooth Config | Default Pin |
|---------------|-------------------|-------------|
| `[CONTROLS] picture_btn_pin` | `[controls] capture_button_pin` | 11 |
| `[CONTROLS] picture_led_pin` | `[controls] capture_led_pin` | 15 |
| `[CONTROLS] print_btn_pin` | `[controls] print_button_pin` | 7 |
| `[CONTROLS] print_led_pin` | `[controls] print_led_pin` | 13 |

The default pins are the same as pibooth's defaults. If you haven't changed them, no config update is needed.

Both projects use BOARD pin numbering via gpiozero. Buttons use internal pull-up resistors and connect to ground.

---

## Hardware Compatibility

### Cameras

| Camera | pibooth | photobooth |
|--------|---------|------------|
| Pi Camera v1/v2 | picamera (legacy) | picamera2 |
| Pi Camera v3 | Not supported | picamera2 (native) |
| USB Webcam | OpenCV | OpenCV |
| DSLR (gphoto2) | gPhoto2 | gPhoto2 (planned) |
| Hybrid (Pi preview + DSLR capture) | Supported | Planned |

### Printers

Any CUPS-compatible printer works with both projects. No changes needed to your printer setup.

### Buttons and LEDs

Same gpiozero library, same wiring. Works identically.

---

## Step-by-Step Walkthrough

### 1. Back Up Your pibooth Installation

```bash
# Back up your config
cp ~/.config/pibooth/pibooth.cfg ~/pibooth-backup.cfg

# Back up your photos
cp -r ~/Pictures/pibooth ~/pibooth-photos-backup
```

### 2. Install photobooth

```bash
# Clone the repo
git clone https://github.com/yourusername/photobooth
cd photobooth

# On Raspberry Pi -- full setup
deploy/setup.sh

# Or for development
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Import Your Config

```bash
# Start the server
uvicorn app.main:app --reload

# Import via API
curl -X POST http://localhost:8000/api/admin/config/import \
  -F "file=@~/pibooth-backup.cfg"
```

Or open `http://localhost:8000/admin` and use the import feature in the UI.

### 4. Review and Adjust

Open `config.toml` and review the imported settings. Key things to check:

- `camera.backend` -- set to `"picamera2"` if using a Pi Camera, `"opencv"` for webcam
- `picture.layout_template` -- choose from the 9 built-in templates (pibooth's layout matrix doesn't map directly)
- `printer.printer_name` -- verify it matches your CUPS printer name (`lpstat -a`)
- `sharing.event_name` -- set your event name

### 5. Test

```bash
# Start the server
uvicorn app.main:app --reload

# Open in browser
# Booth UI:  http://localhost:8000/booth
# Admin:     http://localhost:8000/admin
# Gallery:   http://localhost:8000/gallery
```

Test the full flow: idle -> choose -> capture -> review -> print. Verify GPIO buttons work (if on Pi).

### 6. Deploy

```bash
# On the Pi, restart the systemd service
sudo systemctl restart photobooth

# Check status
sudo systemctl status photobooth

# View logs
sudo journalctl -u photobooth -f
```

### 7. (Optional) Migrate Plugins

If you have pibooth plugins, see the [Plugin Migration](#plugin-migration) section above. The hook patterns are similar enough that most plugins can be ported in a few minutes.
