"""Tests for chromakey (green screen) processing."""

from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app.processing.chromakey import apply_chromakey, list_backgrounds


def test_chromakey_basic():
    """Green image + blue background -> result is mostly blue."""
    green = Image.new("RGB", (100, 100), (0, 255, 0))
    blue = Image.new("RGB", (100, 100), (0, 0, 255))

    result = apply_chromakey(green, blue)

    # Sample center pixel - should be close to blue, not green
    pixel = result.getpixel((50, 50))
    assert pixel[1] < 200, f"Green channel too high: {pixel}"
    assert pixel[2] > 100 or pixel[0] > 100, f"Expected background color: {pixel}"


def test_chromakey_preserves_non_green():
    """Red half should be preserved, green half replaced."""
    img = Image.new("RGB", (100, 100), (255, 0, 0))
    # Make right half green
    for x in range(50, 100):
        for y in range(100):
            img.putpixel((x, y), (0, 255, 0))

    blue = Image.new("RGB", (100, 100), (0, 0, 255))
    result = apply_chromakey(img, blue)

    # Left side (red) should still be red-ish
    left_pixel = result.getpixel((25, 50))
    assert left_pixel[0] > 200, f"Red not preserved on left: {left_pixel}"

    # Right side (was green) should now be blue-ish
    right_pixel = result.getpixel((75, 50))
    assert right_pixel[1] < 200, f"Green not replaced on right: {right_pixel}"


def test_chromakey_pil_fallback():
    """Verify PIL fallback works when cv2 is not available."""
    green = Image.new("RGB", (50, 50), (0, 255, 0))
    blue = Image.new("RGB", (50, 50), (0, 0, 255))

    with patch.dict("sys.modules", {"cv2": None, "numpy": None}):
        result = apply_chromakey(green, blue)

    assert result.size == (50, 50)
    pixel = result.getpixel((25, 25))
    # Should have replaced green with blue
    assert pixel[1] < 200, f"Green channel too high in fallback: {pixel}"


def test_list_backgrounds_empty(tmp_path: Path):
    """Empty or missing dir returns empty list."""
    missing = tmp_path / "no_such_dir"
    assert list_backgrounds(missing) == []


def test_list_backgrounds_with_files(tmp_path: Path):
    """Lists image files from the backgrounds directory."""
    (tmp_path / "beach.jpg").touch()
    (tmp_path / "mountains.png").touch()
    (tmp_path / "notes.txt").touch()  # Should be excluded

    result = list_backgrounds(tmp_path)
    assert "beach.jpg" in result
    assert "mountains.png" in result
    assert "notes.txt" not in result
    assert len(result) == 2
