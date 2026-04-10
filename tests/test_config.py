"""Tests for configuration loading and saving."""

from pathlib import Path

import tomli_w

from app.config import load_config, save_config
from app.models.config_schema import AppConfig


def test_load_default_config(tmp_path: Path) -> None:
    """Loading from a non-existent file returns all defaults."""
    config = load_config(tmp_path / "missing.toml")

    assert config.general.language == "en"
    assert config.general.debug is False
    assert config.camera.backend == "auto"
    assert config.camera.preview_resolution == (1920, 1080)
    assert config.picture.capture_count == 4
    assert config.printer.enabled is True
    assert config.server.port == 8000
    assert config.plugin.enabled == []


def test_load_config_from_file(tmp_path: Path) -> None:
    """Values in TOML override defaults."""
    toml_path = tmp_path / "custom.toml"
    data = {
        "general": {"language": "fr", "debug": True},
        "camera": {"backend": "picamera2", "rotation": 180},
        "server": {"port": 9000},
    }
    with open(toml_path, "wb") as f:
        tomli_w.dump(data, f)

    config = load_config(toml_path)

    assert config.general.language == "fr"
    assert config.general.debug is True
    assert config.camera.backend == "picamera2"
    assert config.camera.rotation == 180
    assert config.server.port == 9000
    # Defaults still intact for untouched sections
    assert config.printer.enabled is True
    assert config.display.fullscreen is True


def test_save_and_reload_config(tmp_path: Path) -> None:
    """Round-trip: save then load preserves all values."""
    toml_path = tmp_path / "roundtrip.toml"
    original = AppConfig()
    original.general.language = "de"
    original.camera.rotation = 90
    original.sharing.event_name = "Wedding"

    save_config(original, toml_path)
    reloaded = load_config(toml_path)

    assert reloaded.general.language == "de"
    assert reloaded.camera.rotation == 90
    assert reloaded.sharing.event_name == "Wedding"
    # Tuple survives the round-trip (TOML stores as array)
    assert reloaded.camera.preview_resolution == (1920, 1080)
    assert reloaded.camera.still_resolution == (4608, 2592)


def test_partial_config(tmp_path: Path) -> None:
    """A TOML with only some sections fills in the rest with defaults."""
    toml_path = tmp_path / "partial.toml"
    data = {
        "sharing": {"event_name": "Birthday Party", "qr_size": 300},
    }
    with open(toml_path, "wb") as f:
        tomli_w.dump(data, f)

    config = load_config(toml_path)

    assert config.sharing.event_name == "Birthday Party"
    assert config.sharing.qr_size == 300
    # Everything else is default
    assert config.general.language == "en"
    assert config.camera.backend == "auto"
    assert config.picture.dpi == 600
    assert config.chromakey.enabled is False
    assert config.controls.debounce_ms == 300
