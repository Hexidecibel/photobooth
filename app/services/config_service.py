"""Pibooth config import service.

Reads a pibooth INI config (~/.config/pibooth/pibooth.cfg) and converts
it to our AppConfig TOML-based format, mapping relevant options and
dropping legacy/pygame-specific ones.
"""

import ast
import configparser
import logging
from pathlib import Path

from app.models.config_schema import AppConfig

logger = logging.getLogger(__name__)


def import_pibooth_config(ini_path: Path) -> tuple[AppConfig, list[str]]:
    """Parse a pibooth INI config and convert to our AppConfig format.

    Maps pibooth config options to our TOML structure, dropping
    options that no longer apply (pygame-specific, legacy camera, etc.)
    and converting formats as needed.

    Returns:
        Tuple of (AppConfig, list of warning strings).
    """
    cp = configparser.RawConfigParser()
    cp.read(ini_path)

    config_dict: dict = {}
    warnings: list[str] = []

    # --- General ---
    general: dict = {}
    if cp.has_option("GENERAL", "language"):
        general["language"] = cp.get("GENERAL", "language")
    if cp.has_option("GENERAL", "directory"):
        general["save_dir"] = cp.get("GENERAL", "directory")
    if cp.has_option("GENERAL", "debug"):
        general["debug"] = _parse_bool(cp.get("GENERAL", "debug"))
    if general:
        config_dict["general"] = general

    # --- Camera ---
    camera: dict = {}
    if cp.has_option("CAMERA", "flip"):
        camera["flip_horizontal"] = _parse_bool(cp.get("CAMERA", "flip"))
    if cp.has_option("CAMERA", "rotation"):
        camera["rotation"] = _parse_int(cp.get("CAMERA", "rotation"), 0)
    if cp.has_option("CAMERA", "resolution"):
        res = _parse_tuple(cp.get("CAMERA", "resolution"))
        if res and len(res) == 2:
            camera["still_resolution"] = list(res)
    # Note: iso, delete_internal_memory are dropped (picamera2 handles differently)
    if camera:
        config_dict["camera"] = camera

    # --- Picture ---
    picture: dict = {}
    if cp.has_option("PICTURE", "orientation"):
        picture["orientation"] = cp.get("PICTURE", "orientation")
    if cp.has_option("PICTURE", "captures"):
        caps = _parse_tuple(cp.get("PICTURE", "captures"))
        if caps:
            # pibooth uses a tuple like (4, 1) meaning 4 or 1 captures
            # We take the first value as default
            picture["capture_count"] = int(caps[0])
    if cp.has_option("PICTURE", "footer_text1"):
        picture["footer_text"] = cp.get("PICTURE", "footer_text1")
    if cp.has_option("PICTURE", "overlays"):
        overlay = cp.get("PICTURE", "overlays")
        if overlay and overlay.lower() not in ("none", ""):
            picture["overlay_path"] = overlay
    if cp.has_option("PICTURE", "backgrounds"):
        bg = cp.get("PICTURE", "backgrounds")
        if bg and bg.startswith("("):
            parsed = _parse_tuple(bg)
            if parsed and len(parsed) == 3:
                # RGB tuple -> hex color
                r, g, b = [int(x) for x in parsed]
                picture["background_color"] = f"#{r:02x}{g:02x}{b:02x}"
        elif bg and not bg.startswith("("):
            picture["background_image"] = bg
    if picture:
        config_dict["picture"] = picture

    # --- Printer ---
    printer: dict = {}
    if cp.has_option("PRINTER", "printer_name"):
        printer["printer_name"] = cp.get("PRINTER", "printer_name")
    if cp.has_option("PRINTER", "auto_print"):
        printer["auto_print"] = _parse_bool(cp.get("PRINTER", "auto_print"))
    if cp.has_option("PRINTER", "max_pages"):
        printer["max_pages"] = _parse_int(cp.get("PRINTER", "max_pages"), 0)
    if cp.has_option("PRINTER", "max_duplicates"):
        printer["copies"] = _parse_int(cp.get("PRINTER", "max_duplicates"), 1)
    if printer:
        config_dict["printer"] = printer

    # --- Controls (GPIO) ---
    controls: dict = {}
    pin_map = {
        "picture_btn_pin": "capture_button_pin",
        "picture_led_pin": "capture_led_pin",
        "print_btn_pin": "print_button_pin",
        "print_led_pin": "print_led_pin",
    }
    for old_key, new_key in pin_map.items():
        if cp.has_option("CONTROLS", old_key):
            controls[new_key] = _parse_int(cp.get("CONTROLS", old_key), 0)
    if cp.has_option("CONTROLS", "debounce_delay"):
        # pibooth uses seconds, we use ms
        delay_s = _parse_float(cp.get("CONTROLS", "debounce_delay"), 0.3)
        controls["debounce_ms"] = int(delay_s * 1000)
    if controls:
        config_dict["controls"] = controls

    # --- Display ---
    display: dict = {}
    if cp.has_option("WINDOW", "size"):
        size_str = cp.get("WINDOW", "size")
        if size_str.strip().lower() == "fullscreen":
            display["fullscreen"] = True
        else:
            size = _parse_tuple(size_str)
            if size and len(size) == 2:
                display["width"] = int(size[0])
                display["height"] = int(size[1])
                display["fullscreen"] = False
    if display:
        config_dict["display"] = display

    # Log dropped options
    dropped = [
        "WINDOW.font",
        "WINDOW.text_color",
        "WINDOW.arrows",
        "WINDOW.animate",
        "PICTURE.captures_effects",
        "PICTURE.captures_cropping",
        "PICTURE.margin_thick",
        "CAMERA.iso",
        "CAMERA.delete_internal_memory",
        "GENERAL.vkeyboard",
        "GENERAL.plugins",
        "GENERAL.plugins_disabled",
    ]
    for key in dropped:
        section, option = key.split(".")
        if cp.has_option(section, option):
            warnings.append(f"Dropped: [{section}] {option} (not applicable)")

    if warnings:
        for w in warnings:
            logger.info(w)

    config = AppConfig(**config_dict)
    return config, warnings


def _parse_bool(val: str) -> bool:
    """Parse a boolean value from pibooth config."""
    return val.strip().lower() in ("true", "yes", "1", "on")


def _parse_int(val: str, default: int = 0) -> int:
    """Parse an integer value, returning default on failure."""
    try:
        return int(val.strip())
    except (ValueError, TypeError):
        return default


def _parse_float(val: str, default: float = 0.0) -> float:
    """Parse a float value, returning default on failure."""
    try:
        return float(val.strip())
    except (ValueError, TypeError):
        return default


def _parse_tuple(val: str) -> tuple | None:
    """Parse pibooth tuple format: (1, 2, 3)."""
    try:
        result = ast.literal_eval(val.strip())
        if isinstance(result, tuple):
            return result
        return None
    except (ValueError, SyntaxError):
        return None
