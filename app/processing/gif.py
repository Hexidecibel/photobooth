"""GIF and boomerang assembly from capture sequences."""

import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


def create_gif(
    frames: list[Path],
    output: Path,
    duration_ms: int = 100,
    resize: tuple[int, int] = (800, 600),
    optimize: bool = True,
) -> Path:
    """Create an animated GIF from a sequence of frames."""
    if not frames:
        raise ValueError("No frames provided")

    images = []
    for f in frames:
        img = Image.open(f).convert("RGB")
        if resize:
            img = img.resize(resize, Image.LANCZOS)
        images.append(img)

    output.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        str(output),
        save_all=True,
        append_images=images[1:],
        duration=duration_ms,
        loop=0,
        optimize=optimize,
    )

    logger.info("GIF created: %s (%d frames)", output, len(images))
    return output


def create_boomerang(
    frames: list[Path],
    output: Path,
    duration_ms: int = 80,
    resize: tuple[int, int] = (800, 600),
    optimize: bool = True,
) -> Path:
    """Create a boomerang GIF (forward + reverse) from frames."""
    if not frames:
        raise ValueError("No frames provided")

    images = []
    for f in frames:
        img = Image.open(f).convert("RGB")
        if resize:
            img = img.resize(resize, Image.LANCZOS)
        images.append(img)

    # Create boomerang: forward + reverse (minus first and last to avoid stutter)
    if len(images) > 2:
        boomerang = images + images[-2:0:-1]
    else:
        boomerang = images + list(reversed(images))

    output.parent.mkdir(parents=True, exist_ok=True)
    boomerang[0].save(
        str(output),
        save_all=True,
        append_images=boomerang[1:],
        duration=duration_ms,
        loop=0,
        optimize=optimize,
    )

    logger.info("Boomerang created: %s (%d frames)", output, len(boomerang))
    return output


def gif_to_bytes(gif_path: Path) -> bytes:
    """Read a GIF file and return bytes (for serving via API)."""
    return gif_path.read_bytes()
