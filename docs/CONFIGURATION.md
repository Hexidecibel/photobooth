# Configuration Reference

All configuration lives in `config.toml` at the project root. Every option has a sensible default -- the booth works out of the box with zero configuration.

You can edit `config.toml` directly or use the web admin panel at `/admin`.

## Table of Contents

- [general](#general)
- [camera](#camera)
- [picture](#picture)
- [chromakey](#chromakey)
- [printer](#printer)
- [controls](#controls)
- [display](#display)
- [sharing](#sharing)
- [server](#server)
- [network](#network)
- [email](#email)
- [sound](#sound)
- [branding](#branding)
- [plugin](#plugin)
- [Full Default Config](#full-default-config)

---

## general

General application settings.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `language` | string | `"en"` | UI language code. Supported: en, fr, de, es, it, pt, nl, pl, da, sv, no, fi, ja, zh. |
| `save_dir` | string | `"data"` | Directory for photos, gallery database, and counters. Relative to project root. |
| `debug` | bool | `false` | Enable debug logging. |
| `autostart_delay` | int | `3` | Seconds to wait before starting the booth loop after server start. |

```toml
[general]
language = "en"
save_dir = "data"
debug = false
autostart_delay = 3
```

---

## camera

Camera hardware and capture settings.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `backend` | string | `"auto"` | Camera backend: `"auto"`, `"picamera2"`, or `"opencv"`. Auto-detection tries picamera2 first, then OpenCV. |
| `preview_resolution` | [int, int] | `[1920, 1080]` | Resolution for the live preview stream (MJPEG). |
| `still_resolution` | [int, int] | `[4608, 2592]` | Resolution for still captures. Use the camera's max resolution for best print quality. |
| `webcam_index` | int | `0` | OpenCV camera index (usually 0 for the first webcam). Only used with the opencv backend. |
| `flip_horizontal` | bool | `false` | Mirror the captured image horizontally. |
| `rotation` | int | `0` | Rotation in degrees (0, 90, 180, 270). |
| `crop_x` | float | `0.0` | Left edge of crop region (0.0-1.0). |
| `crop_y` | float | `0.0` | Top edge of crop region (0.0-1.0). |
| `crop_width` | float | `1.0` | Width of crop region (0.0-1.0). |
| `crop_height` | float | `1.0` | Height of crop region (0.0-1.0). |
| `zoom` | float | `1.0` | Digital zoom factor. 1.0 = no zoom, 2.0 = 2x center crop. Overrides crop settings. |
| `mirror_preview` | bool | `true` | Mirror the live preview (so it feels like a mirror to guests). |
| `mirror_capture` | bool | `false` | Mirror the final captured image. Usually left off so text reads correctly. |

```toml
[camera]
backend = "auto"
preview_resolution = [1920, 1080]
still_resolution = [4608, 2592]
zoom = 1.0
mirror_preview = true
mirror_capture = false
```

**Crop vs. zoom:** Use `zoom` for simple center-crop zooming. Use `crop_x/y/width/height` for precise region selection (e.g., framing a specific area). When `zoom` is not 1.0, it overrides the crop settings. The admin panel has a live camera framing tool that makes this easy.

---

## picture

Picture layout, effects, and rendering settings.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `orientation` | string | `"portrait"` | Photo orientation: `"portrait"` or `"landscape"`. |
| `capture_count` | int | `4` | Number of photos to capture per session. |
| `default_effect` | string | `"none"` | Default effect applied to captures. See [effects list](#effects). |
| `available_effects` | list[string] | `["none", "bw", "sepia", "vintage", "warm", "cool"]` | Effects shown in the guest effect picker. |
| `pose_prompts` | list[string] | `["Strike a pose!", ...]` | Text prompts shown between captures. One per capture. |
| `layout_template` | string | `"classic-4x6"` | Default layout template name. See [TEMPLATES.md](TEMPLATES.md). |
| `guest_picks_template` | bool | `false` | When true, guests choose their template on the choose screen. |
| `overlay_path` | string | `""` | Path to a PNG overlay composited on top of the final image. Use for borders, frames, watermarks. |
| `background_color` | string | `"#ffffff"` | Background color for the layout (hex). |
| `background_image` | string | `""` | Path to a background image for the layout. Overrides `background_color`. |
| `footer_text` | string | `"{event_name} - {date}"` | Text rendered in the template footer. Variables: `{event_name}`, `{date}`, `{count}`. |
| `dpi` | int | `600` | DPI for the composited output. 600 is print quality. |

Available effects: `none`, `bw`, `sepia`, `vintage`, `warm`, `cool`, `blur`, `sharpen`, `high_contrast`.

```toml
[picture]
orientation = "portrait"
capture_count = 4
default_effect = "none"
layout_template = "classic-4x6"
footer_text = "Sarah & Mike's Wedding - {date}"
dpi = 600
```

---

## chromakey

Green screen / chroma key settings.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable green screen mode. |
| `hue_center` | int | `120` | Center of the hue range to key out (0-360). 120 = green. |
| `hue_range` | int | `40` | Width of the hue range around center. Larger = more tolerant. |
| `backgrounds` | list[string] | `[]` | Paths to background images. Guests pick from these during capture. |

```toml
[chromakey]
enabled = true
hue_center = 120
hue_range = 40
backgrounds = [
    "data/backgrounds/beach.jpg",
    "data/backgrounds/city.jpg",
    "data/backgrounds/space.jpg",
]
```

**Tip:** For best results, use a well-lit, evenly-colored green screen. Adjust `hue_range` if the keying is too aggressive (cutting into skin tones) or too lax (leaving green fringe).

---

## printer

Printer hardware and print job settings.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `true` | Enable printing. When false, the print button and state are skipped. |
| `printer_name` | string | `""` | CUPS printer name. Empty = use default printer. |
| `auto_print` | bool | `false` | Print automatically after capture (no button needed). |
| `max_pages` | int | `0` | Maximum pages to print during the event. 0 = unlimited. |
| `copies` | int | `1` | Number of copies per print job. |

```toml
[printer]
enabled = true
printer_name = "Canon_SELPHY_CP1500"
auto_print = false
max_pages = 200
copies = 1
```

**Finding your printer name:** Run `lpstat -a` to list CUPS printers. The name is the first column.

---

## controls

GPIO pin assignments and hardware button settings. Uses BOARD pin numbering.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `capture_button_pin` | int | `11` | GPIO pin for the capture/left button. |
| `print_button_pin` | int | `7` | GPIO pin for the print/right button. |
| `capture_led_pin` | int | `15` | GPIO pin for the capture LED. |
| `print_led_pin` | int | `13` | GPIO pin for the print LED. |
| `debounce_ms` | int | `300` | Button debounce time in milliseconds. |

```toml
[controls]
capture_button_pin = 11
print_button_pin = 7
capture_led_pin = 15
print_led_pin = 13
debounce_ms = 300
```

**Wiring:** Buttons connect between the GPIO pin and ground (gpiozero uses internal pull-up resistors). LEDs need a current-limiting resistor (220-330 ohm) between the GPIO pin and the LED anode, with the cathode to ground.

---

## display

Screen and kiosk display settings.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `fullscreen` | bool | `true` | Launch kiosk in fullscreen mode. |
| `width` | int | `1024` | Window width in pixels (when not fullscreen). |
| `height` | int | `600` | Window height in pixels (when not fullscreen). |
| `hide_cursor` | bool | `true` | Hide the mouse cursor in kiosk mode. |
| `idle_timeout` | int | `60` | Seconds of inactivity before returning to the idle/attract screen. |

```toml
[display]
fullscreen = true
hide_cursor = true
idle_timeout = 60
```

---

## sharing

Photo sharing and QR code settings.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `true` | Enable photo sharing (QR codes, share links). |
| `base_url` | string | `""` | Base URL for share links. If empty, auto-detected from the server address. If a tunnel is active, the tunnel URL is used automatically. |
| `qr_size` | int | `200` | QR code image size in pixels. |
| `event_name` | string | `"Photo Booth"` | Event name displayed in the gallery and share pages. Also available as `{event_name}` in footer text. |

```toml
[sharing]
enabled = true
event_name = "Sarah & Mike's Wedding"
qr_size = 200
```

---

## server

Web server settings.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `host` | string | `"0.0.0.0"` | Bind address. `0.0.0.0` listens on all interfaces. |
| `port` | int | `8000` | Server port. |

```toml
[server]
host = "0.0.0.0"
port = 8000
```

---

## network

Tunnel and hotspot settings for remote access and sharing.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tunnel_enabled` | bool | `false` | Enable internet tunnel for QR sharing over cellular networks. |
| `tunnel_provider` | string | `"localhost.run"` | Tunnel provider: `"localhost.run"` (zero-install SSH tunnel) or `"custom"`. |
| `tunnel_custom_command` | string | `""` | Custom tunnel command. Only used when provider is `"custom"`. Supports `{port}` and `{name}` placeholders. |
| `tunnel_name` | string | `"photobooth"` | Tunnel name used in URL derivation for custom providers. |
| `tunnel_url_pattern` | string | `"https://{name}.tunnel.cush.rocks"` | URL pattern for custom tunnel providers. |
| `hotspot_enabled` | bool | `false` | Enable WiFi hotspot for offline events (planned). |
| `hotspot_ssid` | string | `"PhotoBooth"` | Hotspot network name. |
| `hotspot_password` | string | `"photobooth"` | Hotspot password. |

```toml
[network]
tunnel_enabled = true
tunnel_provider = "localhost.run"

# Or use a custom tunnel:
# tunnel_provider = "custom"
# tunnel_custom_command = "ngrok http {port}"
# tunnel_url_pattern = "https://{name}.ngrok.io"
```

**Why tunnels?** When guests scan a QR code, their phone needs to reach the booth's server. If the phone is on cellular (not the same WiFi), a tunnel makes the booth accessible over the internet. `localhost.run` works with just SSH -- no account or software to install.

---

## email

Email sharing settings via SMTP.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable email sharing. |
| `smtp_host` | string | `""` | SMTP server hostname. |
| `smtp_port` | int | `587` | SMTP port (587 for TLS, 465 for SSL). |
| `smtp_user` | string | `""` | SMTP username. |
| `smtp_password` | string | `""` | SMTP password. |
| `from_address` | string | `""` | Sender email address. |
| `from_name` | string | `"Photo Booth"` | Sender display name. |
| `subject` | string | `"Your Photo Booth Photo!"` | Email subject line. |
| `body_template` | string | `"Here's your photo from {event_name}! ..."` | Email body. Supports `{event_name}` variable. |

```toml
[email]
enabled = true
smtp_host = "smtp.gmail.com"
smtp_port = 587
smtp_user = "booth@example.com"
smtp_password = "app-password-here"
from_address = "booth@example.com"
from_name = "Photo Booth"
subject = "Your Photo Booth Photo!"
```

**Gmail:** Use an [App Password](https://support.google.com/accounts/answer/185833) (not your regular password).

---

## sound

Sound effects settings.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `true` | Enable sound effects. |
| `countdown_beep` | string | `"sounds/beep.mp3"` | Sound played during countdown. |
| `shutter` | string | `"sounds/shutter.mp3"` | Sound played on capture. |
| `applause` | string | `"sounds/applause.mp3"` | Sound played after processing. |
| `click` | string | `"sounds/click.mp3"` | Sound played on button press. |
| `error` | string | `"sounds/error.mp3"` | Sound played on errors. |
| `volume` | float | `0.8` | Volume level (0.0 to 1.0). |

```toml
[sound]
enabled = true
volume = 0.8
shutter = "sounds/shutter.mp3"
```

Paths are relative to the `app/static/` directory. You can use your own sound files by placing them in the static directory and updating the paths.

---

## branding

Company/event branding settings.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `logo_position` | string | `"top"` | Logo position on the booth screen: `"top"`, `"bottom"`, or `"overlay"`. |
| `logo_size` | int | `120` | Logo height in pixels on the booth screen. |
| `show_on_idle` | bool | `true` | Show the logo on the idle/attract screen. |
| `show_on_prints` | bool | `true` | Include the logo in printed photos. |
| `company_name` | string | `""` | Company or event organizer name. |
| `tagline` | string | `""` | Tagline displayed below the company name. |

```toml
[branding]
logo_position = "top"
logo_size = 120
show_on_idle = true
show_on_prints = true
company_name = "Acme Events"
tagline = "Making memories since 2024"
```

Upload logos via the admin panel at `/admin` or the API at `POST /api/admin/branding/logo`.

---

## plugin

Plugin discovery and loading settings.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | list[string] | `[]` | List of plugin names to enable (for setuptools-discovered plugins). Empty = all discovered plugins are loaded. |
| `paths` | list[string] | `[]` | Filesystem paths to Python files to load as plugins. |

```toml
[plugin]
paths = [
    "/home/pi/my_plugins/cloud_upload.py",
    "/home/pi/my_plugins/custom_effect.py",
]
```

See [PLUGINS.md](PLUGINS.md) for the full plugin development guide.

---

## Full Default Config

This is the complete default `config.toml` with all options:

```toml
[general]
language = "en"
save_dir = "data"
debug = false
autostart_delay = 3

[camera]
backend = "auto"
preview_resolution = [1920, 1080]
still_resolution = [4608, 2592]
webcam_index = 0
flip_horizontal = false
rotation = 0
crop_x = 0.0
crop_y = 0.0
crop_width = 1.0
crop_height = 1.0
zoom = 1.0
mirror_preview = true
mirror_capture = false

[picture]
orientation = "portrait"
capture_count = 4
default_effect = "none"
available_effects = ["none", "bw", "sepia", "vintage", "warm", "cool"]
pose_prompts = ["Strike a pose!", "Silly face!", "Say cheese!", "One more!"]
layout_template = "classic-4x6"
guest_picks_template = false
overlay_path = ""
background_color = "#ffffff"
background_image = ""
footer_text = "{event_name} - {date}"
dpi = 600

[chromakey]
enabled = false
hue_center = 120
hue_range = 40
backgrounds = []

[printer]
enabled = true
printer_name = ""
auto_print = false
max_pages = 0
copies = 1

[controls]
capture_button_pin = 11
print_button_pin = 7
capture_led_pin = 15
print_led_pin = 13
debounce_ms = 300

[display]
fullscreen = true
width = 1024
height = 600
hide_cursor = true
idle_timeout = 60

[sharing]
enabled = true
base_url = ""
qr_size = 200
event_name = "Photo Booth"

[server]
host = "0.0.0.0"
port = 8000

[network]
tunnel_enabled = false
tunnel_provider = "localhost.run"
tunnel_custom_command = ""
tunnel_name = "photobooth"
tunnel_url_pattern = "https://{name}.tunnel.cush.rocks"
hotspot_enabled = false
hotspot_ssid = "PhotoBooth"
hotspot_password = "photobooth"

[sound]
enabled = true
countdown_beep = "sounds/beep.mp3"
shutter = "sounds/shutter.mp3"
applause = "sounds/applause.mp3"
click = "sounds/click.mp3"
error = "sounds/error.mp3"
volume = 0.8

[plugin]
enabled = []
paths = []

[email]
enabled = false
smtp_host = ""
smtp_port = 587
smtp_user = ""
smtp_password = ""
from_address = ""
from_name = "Photo Booth"
subject = "Your Photo Booth Photo!"
body_template = "Here's your photo from {event_name}! Download it below."

[branding]
logo_position = "top"
logo_size = 120
show_on_idle = true
show_on_prints = true
company_name = ""
tagline = ""
```
