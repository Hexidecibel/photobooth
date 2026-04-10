"""Tests for configuration loading and saving."""

from pathlib import Path

import tomli_w

from app.config import _deep_merge, load_config, save_config
from app.models.config_schema import AppConfig


def test_load_default_config(tmp_path: Path) -> None:
    """Loading from non-existent files returns all defaults."""
    config = load_config(
        user_path=tmp_path / "missing.toml",
        defaults_path=tmp_path / "also_missing.toml",
    )

    assert config.general.language == "en"
    assert config.general.debug is False
    assert config.camera.backend == "auto"
    assert config.camera.preview_resolution == (1920, 1080)
    assert config.picture.capture_count == 4
    assert config.printer.enabled is True
    assert config.server.port == 8000
    assert config.plugin.enabled == []


def test_load_config_from_defaults_only(tmp_path: Path) -> None:
    """When only defaults exist (no user config), values come from defaults."""
    defaults_path = tmp_path / "config.defaults.toml"
    data = {
        "general": {"language": "fr"},
        "server": {"port": 9000},
    }
    with open(defaults_path, "wb") as f:
        tomli_w.dump(data, f)

    config = load_config(
        user_path=tmp_path / "missing.toml",
        defaults_path=defaults_path,
    )

    assert config.general.language == "fr"
    assert config.server.port == 9000
    # Untouched sections fall back to AppConfig defaults
    assert config.printer.enabled is True


def test_load_config_user_overrides_defaults(tmp_path: Path) -> None:
    """User config values override defaults."""
    defaults_path = tmp_path / "config.defaults.toml"
    user_path = tmp_path / "config.toml"

    defaults_data = {
        "general": {"language": "en", "debug": False},
        "camera": {"backend": "auto", "rotation": 0},
        "server": {"port": 8000},
    }
    user_data = {
        "general": {"language": "fr", "debug": True},
        "camera": {"backend": "picamera2", "rotation": 180},
        "server": {"port": 9000},
    }

    with open(defaults_path, "wb") as f:
        tomli_w.dump(defaults_data, f)
    with open(user_path, "wb") as f:
        tomli_w.dump(user_data, f)

    config = load_config(user_path=user_path, defaults_path=defaults_path)

    assert config.general.language == "fr"
    assert config.general.debug is True
    assert config.camera.backend == "picamera2"
    assert config.camera.rotation == 180
    assert config.server.port == 9000
    # Defaults still intact for untouched sections
    assert config.printer.enabled is True
    assert config.display.fullscreen is True


def test_user_partial_override(tmp_path: Path) -> None:
    """User config with only some keys merges with full defaults."""
    defaults_path = tmp_path / "config.defaults.toml"
    user_path = tmp_path / "config.toml"

    defaults_data = {
        "general": {"language": "en", "debug": False},
        "camera": {"backend": "auto", "rotation": 0},
    }
    user_data = {
        "general": {"language": "de"},
        # camera section not present -- falls back to defaults
    }

    with open(defaults_path, "wb") as f:
        tomli_w.dump(defaults_data, f)
    with open(user_path, "wb") as f:
        tomli_w.dump(user_data, f)

    config = load_config(user_path=user_path, defaults_path=defaults_path)

    assert config.general.language == "de"
    assert config.general.debug is False  # from defaults
    assert config.camera.backend == "auto"  # from defaults
    assert config.camera.rotation == 0  # from defaults


def test_save_and_reload_config(tmp_path: Path) -> None:
    """Round-trip: save then load preserves all values."""
    user_path = tmp_path / "roundtrip.toml"
    original = AppConfig()
    original.general.language = "de"
    original.camera.rotation = 90
    original.sharing.event_name = "Wedding"

    save_config(original, user_path)
    reloaded = load_config(
        user_path=user_path,
        defaults_path=tmp_path / "no_defaults.toml",
    )

    assert reloaded.general.language == "de"
    assert reloaded.camera.rotation == 90
    assert reloaded.sharing.event_name == "Wedding"
    # Tuple survives the round-trip (TOML stores as array)
    assert reloaded.camera.preview_resolution == (1920, 1080)
    assert reloaded.camera.still_resolution == (4608, 2592)


def test_partial_config(tmp_path: Path) -> None:
    """A TOML with only some sections fills in the rest with defaults."""
    user_path = tmp_path / "partial.toml"
    data = {
        "sharing": {"event_name": "Birthday Party", "qr_size": 300},
    }
    with open(user_path, "wb") as f:
        tomli_w.dump(data, f)

    config = load_config(
        user_path=user_path,
        defaults_path=tmp_path / "no_defaults.toml",
    )

    assert config.sharing.event_name == "Birthday Party"
    assert config.sharing.qr_size == 300
    # Everything else is default
    assert config.general.language == "en"
    assert config.camera.backend == "auto"
    assert config.picture.dpi == 600
    assert config.chromakey.enabled is False
    assert config.controls.debounce_ms == 300


def test_deep_merge() -> None:
    """_deep_merge overlays override onto base recursively."""
    base = {"a": {"x": 1, "y": 2}, "b": 10}
    override = {"a": {"y": 99, "z": 3}, "c": 42}
    result = _deep_merge(base, override)

    assert result is base  # mutates in place
    assert result == {"a": {"x": 1, "y": 99, "z": 3}, "b": 10, "c": 42}


def test_deep_merge_replaces_non_dict() -> None:
    """_deep_merge replaces non-dict values entirely."""
    base = {"a": [1, 2, 3]}
    override = {"a": [4, 5]}
    result = _deep_merge(base, override)

    assert result["a"] == [4, 5]
