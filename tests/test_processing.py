"""Tests for the image processing pipeline."""

from pathlib import Path

import pytest
from PIL import Image

from app.models.config_schema import PictureConfig
from app.models.state import CaptureSession
from app.processing.effects import apply_effect, list_effects
from app.processing.layout import LayoutEngine
from app.processing.pipeline import ProcessingPipeline
from app.processing.templates import list_templates, load_template

TEMPLATES_DIR = Path(__file__).parent.parent / "app" / "static" / "templates"


def _make_image(
    width: int = 800, height: int = 600, color: str = "red"
) -> Image.Image:
    return Image.new("RGB", (width, height), color)


# --------------- effects ---------------


def test_apply_effect_none():
    img = _make_image()
    result = apply_effect(img, "none")
    assert result.size == img.size
    assert result.mode == "RGB"


def test_apply_effect_bw():
    img = _make_image(color="red")
    result = apply_effect(img, "bw")
    assert result.mode == "RGB"
    assert result.size == img.size
    # All channels should be equal for a grayscale-like RGB
    r, g, b = result.split()
    assert list(r.get_flattened_data()) == list(g.get_flattened_data())
    assert list(g.get_flattened_data()) == list(b.get_flattened_data())


def test_apply_effect_sepia():
    img = _make_image(color="gray")
    result = apply_effect(img, "sepia")
    assert result.mode == "RGB"
    # Sepia should produce warmer tones: R >= G >= B for neutral inputs
    r, g, b = result.split()
    r_val = list(r.get_flattened_data())[0]
    g_val = list(g.get_flattened_data())[0]
    b_val = list(b.get_flattened_data())[0]
    assert r_val >= g_val >= b_val


def test_apply_effect_unknown():
    img = _make_image()
    result = apply_effect(img, "nonexistent_effect")
    # Should return passthrough (same image)
    assert result is img


def test_apply_effect_cartoon():
    img = Image.new("RGB", (200, 200), "red")
    result = apply_effect(img, "cartoon")
    assert result.mode == "RGB"
    assert result.size == (200, 200)


def test_apply_effect_pencil_sketch():
    img = Image.new("RGB", (200, 200), "red")
    result = apply_effect(img, "pencil_sketch")
    assert result.mode == "RGB"
    assert result.size == (200, 200)


def test_apply_effect_watercolor():
    img = Image.new("RGB", (200, 200), "red")
    result = apply_effect(img, "watercolor")
    assert result.mode == "RGB"
    assert result.size == (200, 200)


def test_apply_effect_pop_art():
    img = Image.new("RGB", (200, 200), "red")
    result = apply_effect(img, "pop_art")
    assert result.mode == "RGB"
    assert result.size == (200, 200)


def test_apply_effect_oil_painting():
    img = Image.new("RGB", (200, 200), "red")
    result = apply_effect(img, "oil_painting")
    assert result.mode == "RGB"
    assert result.size == (200, 200)


def test_list_effects_includes_new():
    effects = list_effects()
    for name in ["cartoon", "pencil_sketch", "watercolor", "pop_art", "oil_painting"]:
        assert name in effects, f"{name} not in list_effects()"


def test_list_effects():
    effects = list_effects()
    assert isinstance(effects, list)
    assert "none" in effects
    assert "bw" in effects
    assert "sepia" in effects
    assert len(effects) == 14


# --------------- templates ---------------


def test_load_template():
    template = load_template("classic-4x6", templates_dir=TEMPLATES_DIR)
    assert template.name == "classic-4x6"
    assert len(template.slots) == 4
    assert template.width_px == int(4 * 600)
    assert template.height_px == int(6 * 600)
    assert template.footer is not None


def test_load_template_not_found():
    with pytest.raises(FileNotFoundError):
        load_template("nonexistent-template", templates_dir=TEMPLATES_DIR)


def test_list_templates():
    names = list_templates(templates_dir=TEMPLATES_DIR)
    assert isinstance(names, list)
    assert "classic-4x6" in names
    assert "strip-2x6" in names
    assert "single" in names


# --------------- layout engine ---------------


def test_layout_engine_compose():
    template = load_template("classic-4x6", templates_dir=TEMPLATES_DIR)
    captures = [
        _make_image(color="red"),
        _make_image(color="green"),
        _make_image(color="blue"),
        _make_image(color="yellow"),
    ]
    engine = LayoutEngine()
    result = engine.compose(captures, template)
    assert result.size == (template.width_px, template.height_px)
    assert result.mode == "RGB"


def test_layout_engine_fewer_captures():
    template = load_template("classic-4x6", templates_dir=TEMPLATES_DIR)
    captures = [
        _make_image(color="red"),
        _make_image(color="green"),
    ]
    engine = LayoutEngine()
    result = engine.compose(captures, template)
    assert result.size == (template.width_px, template.height_px)


# --------------- full pipeline ---------------


@pytest.fixture
def tmp_captures(tmp_path: Path) -> list[Path]:
    """Create temporary capture images on disk."""
    paths = []
    for i, color in enumerate(["red", "green", "blue", "yellow"]):
        p = tmp_path / f"capture_{i}.jpg"
        _make_image(color=color).save(str(p), "JPEG")
        paths.append(p)
    return paths


async def test_pipeline_process(tmp_path: Path, tmp_captures: list[Path]):
    session = CaptureSession(
        captures=tmp_captures,
        selected_effect="none",
        layout_template="classic-4x6",
    )
    config = PictureConfig()

    pipeline = ProcessingPipeline()
    output = await pipeline.process(session, config, save_dir=str(tmp_path))

    assert output.exists()
    assert output.suffix == ".jpg"
    assert session.composite_path == output

    # Verify it's a valid image
    img = Image.open(output)
    assert img.mode == "RGB"
