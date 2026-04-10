"""Configuration loading and saving.

Uses stdlib tomllib for reading and tomli_w for writing TOML files.

Config layering:
  1. config.defaults.toml  -- tracked in git, updated with new features
  2. config.toml           -- user overrides, gitignored
"""

import tomllib
from pathlib import Path

import tomli_w

from app.models.config_schema import AppConfig


def load_config(
    user_path: Path = Path("config.toml"),
    defaults_path: Path = Path("config.defaults.toml"),
) -> AppConfig:
    """Load config: defaults first, then user overrides.

    Missing keys in user config fall back to defaults.
    If neither file exists, returns an AppConfig with all defaults.
    """
    data: dict = {}

    # Load defaults
    if defaults_path.exists():
        with open(defaults_path, "rb") as f:
            data = tomllib.load(f)

    # Overlay user config
    if user_path.exists():
        with open(user_path, "rb") as f:
            user_data = tomllib.load(f)
        _deep_merge(data, user_data)

    return AppConfig(**data)


def save_config(
    config: AppConfig, path: Path = Path("config.toml")
) -> None:
    """Serialize an AppConfig to TOML and write it to the user config."""
    data = config.model_dump()
    # Convert tuples to lists for TOML compatibility
    _convert_tuples(data)

    with open(path, "wb") as f:
        tomli_w.dump(data, f)


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base, mutating base in place."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _convert_tuples(obj: dict | list) -> None:
    """Recursively convert tuples to lists inside a nested structure.

    TOML only supports arrays (lists), not tuples. Pydantic's
    model_dump() preserves tuple types, so we normalise them here.
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, tuple):
                obj[key] = list(value)
            elif isinstance(value, (dict, list)):
                _convert_tuples(value)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            if isinstance(value, tuple):
                obj[i] = list(value)
            elif isinstance(value, (dict, list)):
                _convert_tuples(value)
