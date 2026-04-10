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


def create_templated_gif(
    frames: list[Path],
    output: Path,
    template_name: str = "single",
    footer_vars: dict | None = None,
    effect: str | None = None,
    duration_ms: int = 100,
    resize_width: int = 600,
    chromakey_background: str | None = None,
    chromakey_hue_center: int = 120,
    chromakey_hue_range: int = 40,
) -> Path:
    """Create an animated GIF with each frame composited into a template."""
    from app.processing.chromakey import apply_chromakey
    from app.processing.effects import apply_effect
    from app.processing.layout import LayoutEngine
    from app.processing.templates import load_template

    template = load_template(template_name)
    engine = LayoutEngine()

    # Load chromakey background if specified
    ck_bg = None
    if chromakey_background:
        bg_dir = Path(__file__).parent.parent / "static" / "backgrounds"
        bg_path = bg_dir / chromakey_background
        if bg_path.exists():
            ck_bg = Image.open(bg_path)

    # Calculate output size maintaining template aspect ratio
    aspect = template.width_inches / template.height_inches
    out_w = resize_width
    out_h = int(out_w / aspect)

    composed_frames = []
    for frame_path in frames:
        img = Image.open(frame_path).convert("RGB")

        # Apply chromakey before effects
        if ck_bg:
            img = apply_chromakey(img, ck_bg, chromakey_hue_center, chromakey_hue_range)

        # Apply effect if selected
        if effect and effect != "none":
            img = apply_effect(img, effect)

        # Compose into template (single frame as a 1-element list)
        composite = engine.compose([img], template, footer_vars or {})

        # Resize for GIF (full template res is too big)
        composite = composite.resize((out_w, out_h), Image.LANCZOS)
        composed_frames.append(composite)

    if not composed_frames:
        raise ValueError("No frames to process")

    output.parent.mkdir(parents=True, exist_ok=True)
    composed_frames[0].save(
        str(output),
        save_all=True,
        append_images=composed_frames[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )

    logger.info("Templated GIF created: %s (%d frames)", output, len(composed_frames))
    return output


def create_templated_boomerang(
    frames: list[Path],
    output: Path,
    template_name: str = "single",
    footer_vars: dict | None = None,
    effect: str | None = None,
    duration_ms: int = 80,
    resize_width: int = 600,
    chromakey_background: str | None = None,
    chromakey_hue_center: int = 120,
    chromakey_hue_range: int = 40,
) -> Path:
    """Create a boomerang GIF (forward+reverse) with template framing."""
    from app.processing.chromakey import apply_chromakey
    from app.processing.effects import apply_effect
    from app.processing.layout import LayoutEngine
    from app.processing.templates import load_template

    template = load_template(template_name)
    engine = LayoutEngine()

    # Load chromakey background if specified
    ck_bg = None
    if chromakey_background:
        bg_dir = Path(__file__).parent.parent / "static" / "backgrounds"
        bg_path = bg_dir / chromakey_background
        if bg_path.exists():
            ck_bg = Image.open(bg_path)

    aspect = template.width_inches / template.height_inches
    out_w = resize_width
    out_h = int(out_w / aspect)

    composed_frames = []
    for frame_path in frames:
        img = Image.open(frame_path).convert("RGB")
        # Apply chromakey before effects
        if ck_bg:
            img = apply_chromakey(img, ck_bg, chromakey_hue_center, chromakey_hue_range)
        if effect and effect != "none":
            img = apply_effect(img, effect)
        composite = engine.compose([img], template, footer_vars or {})
        composite = composite.resize((out_w, out_h), Image.LANCZOS)
        composed_frames.append(composite)

    if not composed_frames:
        raise ValueError("No frames to process")

    # Boomerang: forward + reverse (minus endpoints)
    if len(composed_frames) > 2:
        boomerang = composed_frames + composed_frames[-2:0:-1]
    else:
        boomerang = composed_frames + list(reversed(composed_frames))

    output.parent.mkdir(parents=True, exist_ok=True)
    boomerang[0].save(
        str(output),
        save_all=True,
        append_images=boomerang[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )

    logger.info(
        "Templated boomerang created: %s (%d frames)", output, len(boomerang)
    )
    return output


def gif_to_bytes(gif_path: Path) -> bytes:
    """Read a GIF file and return bytes (for serving via API)."""
    return gif_path.read_bytes()
