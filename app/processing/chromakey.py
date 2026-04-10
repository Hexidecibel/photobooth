"""Green screen compositing using OpenCV (optional) or pure PIL fallback."""

import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


def apply_chromakey(
    foreground: Image.Image,
    background: Image.Image,
    hue_center: int = 120,
    hue_range: int = 40,
    saturation_min: int = 50,
) -> Image.Image:
    """Replace green screen with background image.

    Uses OpenCV if available for better quality, falls back to pure PIL.
    """
    try:
        return _chromakey_opencv(
            foreground, background, hue_center, hue_range, saturation_min
        )
    except ImportError:
        return _chromakey_pil(
            foreground, background, hue_center, hue_range, saturation_min
        )


def _chromakey_opencv(
    foreground: Image.Image,
    background: Image.Image,
    hue_center: int,
    hue_range: int,
    sat_min: int,
) -> Image.Image:
    """OpenCV-based chromakey with feathered edges."""
    import cv2
    import numpy as np

    fg = np.array(foreground.convert("RGB"))
    bg = np.array(background.convert("RGB").resize(foreground.size, Image.LANCZOS))

    # Convert to HSV
    hsv = cv2.cvtColor(fg, cv2.COLOR_RGB2HSV)

    # Convert hue from 0-360 degree scale to OpenCV's 0-179 scale
    cv_hue = hue_center * 179 // 360
    cv_range = hue_range * 179 // 360

    # Create mask for the green screen
    lower = np.array([max(0, cv_hue - cv_range), sat_min, 50])
    upper = np.array([min(179, cv_hue + cv_range), 255, 255])
    mask = cv2.inRange(hsv, lower, upper)

    # Feather the edges for smooth blending
    mask = cv2.GaussianBlur(mask, (7, 7), 0)

    # Create inverse mask
    mask_inv = cv2.bitwise_not(mask)

    # Extract foreground and background parts
    fg_part = cv2.bitwise_and(fg, fg, mask=mask_inv)
    bg_part = cv2.bitwise_and(bg, bg, mask=mask)

    # Combine
    result = cv2.add(fg_part, bg_part)
    return Image.fromarray(result)


def _chromakey_pil(
    foreground: Image.Image,
    background: Image.Image,
    hue_center: int,
    hue_range: int,
    sat_min: int,
) -> Image.Image:
    """Pure PIL fallback for chromakey. Less smooth but works without OpenCV."""
    fg = foreground.convert("RGB")
    bg = background.convert("RGB").resize(fg.size, Image.LANCZOS)

    # Convert to HSV-like using PIL
    fg_hsv = fg.convert("HSV")
    pixels_bg = bg.load()
    pixels_hsv = fg_hsv.load()

    result = fg.copy()
    pixels_result = result.load()

    w, h = fg.size
    for y in range(h):
        for x in range(w):
            h_val, s_val, v_val = pixels_hsv[x, y]
            # PIL HSV: H is 0-255; convert to 0-360 degree scale
            h_deg = h_val * 360 // 255
            if (
                abs(h_deg - hue_center) <= hue_range
                and s_val > (sat_min * 255 // 100)
                and v_val > 50
            ):
                pixels_result[x, y] = pixels_bg[x, y]

    return result


def list_backgrounds(backgrounds_dir: Path | None = None) -> list[str]:
    """List available background images for green screen."""
    if backgrounds_dir is None:
        backgrounds_dir = Path(__file__).parent.parent / "static" / "backgrounds"
    if not backgrounds_dir.exists():
        return []
    extensions = {".jpg", ".jpeg", ".png", ".webp"}
    return [
        p.name
        for p in sorted(backgrounds_dir.iterdir())
        if p.suffix.lower() in extensions
    ]
