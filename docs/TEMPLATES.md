# Template Guide

Templates define how captured photos are arranged into a final composited image for display and printing. Each template is a JSON file that specifies the canvas size, photo slot positions, and optional footer text.

## Table of Contents

- [JSON Format](#json-format)
- [Slot Coordinates](#slot-coordinates)
- [Built-in Templates](#built-in-templates)
- [Creating Templates](#creating-templates)
  - [Visual Editor](#visual-editor)
  - [Manual Creation](#manual-creation)
- [Footer Variables](#footer-variables)
- [Tips](#tips)

---

## JSON Format

Templates are stored as JSON files in `app/static/templates/`. Each file defines one layout:

```json
{
    "name": "my-template",
    "width_inches": 4,
    "height_inches": 6,
    "dpi": 600,
    "background": "#ffffff",
    "slots": [
        {"x": 0.05, "y": 0.03, "width": 0.9, "height": 0.45, "rotation": 0},
        {"x": 0.05, "y": 0.50, "width": 0.9, "height": 0.45, "rotation": 0}
    ],
    "footer": {
        "y": 0.95,
        "height": 0.04,
        "text": "{event_name} - {date}",
        "font_size": 18,
        "color": "#333333"
    }
}
```

### Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Template identifier. Must match the filename (without `.json`). |
| `width_inches` | float | Yes | Canvas width in inches. Common: 4 (4x6), 2 (2x6 strip). |
| `height_inches` | float | Yes | Canvas height in inches. Common: 6 (4x6, 2x6). |
| `dpi` | int | No | Dots per inch. Default: 600. Determines pixel dimensions. |
| `background` | string | No | Hex color (e.g., `"#ffffff"`) or path to a background image. Default: `"#ffffff"`. |
| `slots` | array | Yes | Array of slot objects defining where photos are placed. |
| `footer` | object | No | Footer text specification. Omit for no footer. |

### Slot Object

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `x` | float | -- | Left edge position (0.0-1.0). |
| `y` | float | -- | Top edge position (0.0-1.0). |
| `width` | float | -- | Slot width (0.0-1.0). |
| `height` | float | -- | Slot height (0.0-1.0). |
| `rotation` | float | `0.0` | Rotation in degrees. Positive = clockwise. |

### Footer Object

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `y` | float | -- | Top edge of footer area (0.0-1.0). |
| `height` | float | -- | Height of footer area (0.0-1.0). |
| `text` | string | `""` | Footer text. Supports variables (see [Footer Variables](#footer-variables)). |
| `font_size` | int | `24` | Font size in points. |
| `color` | string | `"#000000"` | Text color (hex). |

---

## Slot Coordinates

All positions and sizes use a **fractional coordinate system** from 0.0 to 1.0, where:

- `x: 0.0` = left edge of the canvas
- `x: 1.0` = right edge of the canvas
- `y: 0.0` = top edge of the canvas
- `y: 1.0` = bottom edge of the canvas

This means templates are resolution-independent. A slot at `{"x": 0.05, "y": 0.03, "width": 0.9, "height": 0.21}` always takes up 90% of the canvas width and 21% of the height, starting 5% from the left and 3% from the top.

**Pixel conversion:** The actual pixel position is calculated as:

```
pixel_x = x * width_inches * dpi
pixel_y = y * height_inches * dpi
pixel_w = width * width_inches * dpi
pixel_h = height * height_inches * dpi
```

For a 4x6" canvas at 600 DPI, that's a 2400x3600 pixel image. A slot with `width: 0.9` would be 2160 pixels wide.

---

## Built-in Templates

### classic-4x6

Four horizontal photos stacked vertically. The traditional photo booth strip on a 4x6" print.

```
+---------------------------+
|  [    photo 1           ] |
|  [    photo 2           ] |
|  [    photo 3           ] |
|  [    photo 4           ] |
|       footer text         |
+---------------------------+
       4" x 6" @ 600 DPI
```

Slots: 4 | Size: 4x6" | Each slot: 90% width, 21% height

### strip-2x6

Narrow strip format -- four photos in a vertical strip. Classic photo booth strip cut.

```
+-----------+
| [ photo ] |
| [ photo ] |
| [ photo ] |
| [ photo ] |
|  footer   |
+-----------+
  2" x 6"
```

Slots: 4 | Size: 2x6" | Each slot: 90% width, 22% height

### single

One large photo filling the print. Best for single-shot mode.

```
+---------------------------+
|                           |
|                           |
|      [  photo 1  ]       |
|                           |
|                           |
|       footer text         |
+---------------------------+
       4" x 6"
```

Slots: 1 | Size: 4x6" | Slot: 90% width, 85% height

### polaroid-4x6

Polaroid-style layout with a large photo and generous footer area for text.

```
+---------------------------+
|                           |
|      [  photo 1  ]       |
|                           |
|                           |
|                           |
|      event name           |
|                           |
+---------------------------+
       4" x 6"
```

Slots: 1 | Size: 4x6" | Slot: 84% width, 70% height | Large footer area (15%)

### duo-4x6

Two portrait photos side by side. Great for couples or before/after shots.

```
+---------------------------+
|            |              |
| [ photo ]  | [ photo ]   |
|   1        |   2         |
|            |              |
|            |              |
|       footer text         |
+---------------------------+
       4" x 6"
```

Slots: 2 | Size: 4x6" | Each slot: 45% width, 85% height

### triple-4x6

Three horizontal photos stacked. Good for 3-capture sessions.

```
+---------------------------+
|  [    photo 1           ] |
|                           |
|  [    photo 2           ] |
|                           |
|  [    photo 3           ] |
|       footer text         |
+---------------------------+
       4" x 6"
```

Slots: 3 | Size: 4x6" | Each slot: 90% width, 28% height

### collage-4x6

Four photos scattered with slight rotation, creating a casual collage look. Light gray background.

```
+---------------------------+
|  [photo 1]  [photo 2]    |
|     -3deg      +2deg     |
|                           |
|  [photo 3]  [photo 4]    |
|     +1deg      -2deg     |
|       footer text         |
+---------------------------+
       4" x 6"
```

Slots: 4 | Size: 4x6" | Background: `#f5f5f5` | Each slot: 50% width, 35% height | Rotations: -3, +2, +1, -2 degrees

### grid-2x2-4x6

Four photos in a 2x2 grid on a dark background. Modern look.

```
+---------------------------+
| [ photo 1 ] [ photo 2 ]  |
|                           |
| [ photo 3 ] [ photo 4 ]  |
|                           |
|       footer text         |
+---------------------------+
       4" x 6"
```

Slots: 4 | Size: 4x6" | Background: `#1a1a2e` (dark navy) | Footer color: `#ffffff` (white) | Each slot: 45% width, 43% height

### big-small-4x6

One large hero photo on top, two smaller photos below. Emphasizes the best shot.

```
+---------------------------+
|                           |
|  [     photo 1          ]|
|                           |
|  [ photo 2 ] [ photo 3 ] |
|       footer text         |
+---------------------------+
       4" x 6"
```

Slots: 3 | Size: 4x6" | Hero slot: 94% width, 55% height | Small slots: 45% width, 30% height

---

## Creating Templates

### Visual Editor

The admin panel at `/admin` includes a visual template editor:

1. Navigate to Templates in the admin panel
2. Click "New Template" or edit an existing one
3. Set canvas dimensions (inches and DPI)
4. Drag and position photo slots on the canvas
5. Set rotation, background color, and footer text
6. Save -- the template is immediately available for use

### Manual Creation

Create a JSON file in `app/static/templates/`:

```bash
# Create a new template
cat > app/static/templates/my-template.json << 'EOF'
{
    "name": "my-template",
    "width_inches": 4,
    "height_inches": 6,
    "dpi": 600,
    "background": "#f0f0f0",
    "slots": [
        {"x": 0.05, "y": 0.05, "width": 0.9, "height": 0.4, "rotation": 0},
        {"x": 0.05, "y": 0.50, "width": 0.42, "height": 0.4, "rotation": 0},
        {"x": 0.53, "y": 0.50, "width": 0.42, "height": 0.4, "rotation": 0}
    ],
    "footer": {
        "y": 0.93,
        "height": 0.05,
        "text": "{event_name}",
        "font_size": 20,
        "color": "#333333"
    }
}
EOF
```

### Via the API

```bash
# Save a template
curl -X PUT http://localhost:8000/api/admin/templates/my-template \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-template",
    "width_inches": 4,
    "height_inches": 6,
    "dpi": 600,
    "background": "#ffffff",
    "slots": [
        {"x": 0.05, "y": 0.05, "width": 0.9, "height": 0.85}
    ]
  }'

# List all templates
curl http://localhost:8000/api/admin/templates

# Get a template
curl http://localhost:8000/api/admin/templates/my-template

# Delete a template
curl -X DELETE http://localhost:8000/api/admin/templates/my-template
```

---

## Footer Variables

Footer text supports these variables, replaced at render time:

| Variable | Description | Example |
|----------|-------------|---------|
| `{event_name}` | From `sharing.event_name` in config | "Sarah & Mike's Wedding" |
| `{date}` | Current date | "2026-04-09" |
| `{count}` | Photo counter (session total) | "42" |

**Examples:**

```json
"text": "{event_name} - {date}"
// -> "Sarah & Mike's Wedding - 2026-04-09"

"text": "Photo #{count}"
// -> "Photo #42"

"text": "Thanks for celebrating with us!"
// -> "Thanks for celebrating with us!"
```

The footer text in the template can be overridden by the `picture.footer_text` config option.

---

## Tips

### Aspect Ratios

Match slot aspect ratios to your camera's output to avoid cropping. Common camera aspect ratios:

- Pi Camera v3: 4:3 (4608x3456) or 16:9 (crop)
- Most DSLRs: 3:2
- Most webcams: 16:9 or 4:3

For a slot that should hold a 4:3 photo, set the width:height ratio to approximately 4:3 relative to the canvas. On a 4x6" canvas, a slot with `width: 0.9` (3.6") and `height: 0.21` (1.26") gives roughly 3:1 -- very wide. For 4:3, you'd want something like `width: 0.6, height: 0.33` on a 4x6" canvas.

### DPI for Print Quality

| DPI | Quality | Use Case |
|-----|---------|----------|
| 150 | Screen only | Digital sharing, never printed |
| 300 | Good | Standard print quality |
| 600 | Excellent | Professional print quality (default) |

Higher DPI = larger image files = slower processing. 600 DPI on 4x6" = 2400x3600 pixels. 300 DPI = 1200x1800 pixels. If you're only sharing digitally, 300 DPI is fine and processes faster.

### Rotation Effects

Use small rotation values (1-5 degrees) for a casual, scrapbook feel. The `collage-4x6` template demonstrates this well. Large rotations (45, 90) create more dramatic layouts but can clip photos at the canvas edge.

### Background Images

Instead of a solid color, use an image path:

```json
"background": "data/backgrounds/event-border.png"
```

The background image is stretched to fill the canvas. For best results, create it at the exact canvas pixel dimensions (e.g., 2400x3600 for 4x6" at 600 DPI).

### Common Print Sizes

| Size | Typical Use |
|------|-------------|
| 2x6" | Photo strip (cut in half for two strips) |
| 4x6" | Standard photo print (most popular) |
| 5x7" | Larger print, good for single-shot |

### Template Selection by Guests

Enable `picture.guest_picks_template = true` in config to let guests choose their layout on the choose screen. All templates in `app/static/templates/` will be shown as options.
