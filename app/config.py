"""Configuration loading and saving.

Uses stdlib tomllib for reading and tomli_w for writing TOML files.
"""

import tomllib
from pathlib import Path

import tomli_w

from app.models.config_schema import AppConfig


def load_config(path: Path = Path("config.toml")) -> AppConfig:
    """Load configuration from a TOML file.

    If the file does not exist, returns an AppConfig with all defaults.
    """
    if not path.exists():
        return AppConfig()

    with open(path, "rb") as f:
        data = tomllib.load(f)

    return AppConfig(**data)


def save_config(
    config: AppConfig, path: Path = Path("config.toml")
) -> None:
    """Serialize an AppConfig to TOML and write it to disk."""
    data = config.model_dump()
    # Convert tuples to lists for TOML compatibility
    _convert_tuples(data)

    with open(path, "wb") as f:
        tomli_w.dump(data, f)


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
