"""Tests for pibooth config import."""

import configparser
from pathlib import Path

from app.services.config_service import import_pibooth_config


def _make_pibooth_config(tmp_path: Path, sections: dict) -> Path:
    """Create a temporary pibooth-style INI config file."""
    cp = configparser.RawConfigParser()
    for section, options in sections.items():
        cp.add_section(section)
        for key, val in options.items():
            cp.set(section, key, val)
    path = tmp_path / "pibooth.cfg"
    with open(path, "w") as f:
        cp.write(f)
    return path


def test_import_basic_pibooth_config(tmp_path: Path):
    """Known values map correctly to AppConfig fields."""
    path = _make_pibooth_config(
        tmp_path,
        {
            "GENERAL": {"language": "fr", "directory": "/photos", "debug": "True"},
            "CAMERA": {"flip": "True", "rotation": "90"},
            "PICTURE": {"orientation": "landscape", "footer_text1": "My Booth"},
            "PRINTER": {"printer_name": "Canon_Selphy", "auto_print": "True"},
        },
    )
    config, warnings = import_pibooth_config(path)

    assert config.general.language == "fr"
    assert config.general.save_dir == "/photos"
    assert config.general.debug is True
    assert config.camera.flip_horizontal is True
    assert config.camera.rotation == 90
    assert config.picture.orientation == "landscape"
    assert config.picture.footer_text == "My Booth"
    assert config.printer.printer_name == "Canon_Selphy"
    assert config.printer.auto_print is True


def test_import_gpio_pins(tmp_path: Path):
    """Pin mapping: picture_btn_pin -> capture_button_pin, etc."""
    path = _make_pibooth_config(
        tmp_path,
        {
            "CONTROLS": {
                "picture_btn_pin": "21",
                "picture_led_pin": "22",
                "print_btn_pin": "23",
                "print_led_pin": "24",
            },
        },
    )
    config, _ = import_pibooth_config(path)

    assert config.controls.capture_button_pin == 21
    assert config.controls.capture_led_pin == 22
    assert config.controls.print_button_pin == 23
    assert config.controls.print_led_pin == 24


def test_import_debounce_seconds_to_ms(tmp_path: Path):
    """Pibooth 0.3s debounce -> our 300ms."""
    path = _make_pibooth_config(
        tmp_path,
        {"CONTROLS": {"debounce_delay": "0.3"}},
    )
    config, _ = import_pibooth_config(path)

    assert config.controls.debounce_ms == 300


def test_import_captures_tuple(tmp_path: Path):
    """Pibooth (4, 1) captures tuple -> capture_count=4."""
    path = _make_pibooth_config(
        tmp_path,
        {"PICTURE": {"captures": "(4, 1)"}},
    )
    config, _ = import_pibooth_config(path)

    assert config.picture.capture_count == 4


def test_import_background_rgb_to_hex(tmp_path: Path):
    """RGB tuple (255, 0, 128) -> hex #ff0080."""
    path = _make_pibooth_config(
        tmp_path,
        {"PICTURE": {"backgrounds": "(255, 0, 128)"}},
    )
    config, _ = import_pibooth_config(path)

    assert config.picture.background_color == "#ff0080"


def test_import_fullscreen(tmp_path: Path):
    """Window size 'fullscreen' -> fullscreen=True."""
    path = _make_pibooth_config(
        tmp_path,
        {"WINDOW": {"size": "fullscreen"}},
    )
    config, _ = import_pibooth_config(path)

    assert config.display.fullscreen is True


def test_import_window_size(tmp_path: Path):
    """Window size tuple -> width/height with fullscreen=False."""
    path = _make_pibooth_config(
        tmp_path,
        {"WINDOW": {"size": "(800, 480)"}},
    )
    config, _ = import_pibooth_config(path)

    assert config.display.width == 800
    assert config.display.height == 480
    assert config.display.fullscreen is False


def test_import_dropped_options_warnings(tmp_path: Path):
    """Dropped options appear in warnings list."""
    path = _make_pibooth_config(
        tmp_path,
        {
            "CAMERA": {"iso": "400", "delete_internal_memory": "True"},
            "GENERAL": {"vkeyboard": "True", "plugins": "some_plugin"},
            "WINDOW": {"font": "Arial", "text_color": "(0, 0, 0)"},
            "PICTURE": {"captures_effects": "none", "margin_thick": "50"},
        },
    )
    config, warnings = import_pibooth_config(path)

    assert any("iso" in w for w in warnings)
    assert any("delete_internal_memory" in w for w in warnings)
    assert any("vkeyboard" in w for w in warnings)
    assert any("plugins" in w for w in warnings)
    assert any("font" in w for w in warnings)
    assert any("text_color" in w for w in warnings)
    assert any("captures_effects" in w for w in warnings)
    assert any("margin_thick" in w for w in warnings)


def test_import_empty_config(tmp_path: Path):
    """Empty INI produces default AppConfig."""
    path = _make_pibooth_config(tmp_path, {})
    config, warnings = import_pibooth_config(path)

    # Should be defaults
    assert config.general.language == "en"
    assert config.camera.rotation == 0
    assert config.picture.capture_count == 4
    assert warnings == []


def test_import_missing_sections(tmp_path: Path):
    """Partial INI works -- missing sections get defaults."""
    path = _make_pibooth_config(
        tmp_path,
        {"GENERAL": {"language": "de"}},
    )
    config, _ = import_pibooth_config(path)

    assert config.general.language == "de"
    # Other sections should be defaults
    assert config.camera.rotation == 0
    assert config.printer.printer_name == ""
    assert config.controls.debounce_ms == 300
    assert config.display.fullscreen is True
