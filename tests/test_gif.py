"""Tests for GIF and boomerang creation."""

from pathlib import Path

import pytest
from PIL import Image

from app.processing.gif import create_boomerang, create_gif, gif_to_bytes


def _make_frames(tmp_path: Path, count: int = 3) -> list[Path]:
    """Create test frame images."""
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255)]
    frames = []
    for i in range(count):
        p = tmp_path / f"frame_{i}.png"
        Image.new("RGB", (100, 100), colors[i % len(colors)]).save(str(p))
        frames.append(p)
    return frames


def test_create_gif(tmp_path: Path):
    """Create a GIF from test frames and verify output."""
    frames = _make_frames(tmp_path, 3)
    output = tmp_path / "output.gif"

    result = create_gif(frames, output, resize=(80, 60))

    assert result == output
    assert output.exists()
    assert output.stat().st_size > 0

    # Verify it's a valid GIF with correct frame count
    gif = Image.open(str(output))
    assert gif.format == "GIF"
    n_frames = 0
    try:
        while True:
            n_frames += 1
            gif.seek(gif.tell() + 1)
    except EOFError:
        pass
    assert n_frames == 3


def test_create_boomerang(tmp_path: Path):
    """Boomerang should have forward + reverse frames."""
    frames = _make_frames(tmp_path, 4)
    output = tmp_path / "boomerang.gif"

    result = create_boomerang(frames, output, resize=(80, 60))

    assert result == output
    assert output.exists()

    # 4 frames forward + 2 reversed (minus first and last) = 6 total
    gif = Image.open(str(output))
    n_frames = 0
    try:
        while True:
            n_frames += 1
            gif.seek(gif.tell() + 1)
    except EOFError:
        pass
    assert n_frames == 6


def test_create_gif_no_frames(tmp_path: Path):
    """Empty frame list should raise ValueError."""
    output = tmp_path / "empty.gif"
    with pytest.raises(ValueError, match="No frames provided"):
        create_gif([], output)


def test_gif_to_bytes(tmp_path: Path):
    """Read GIF bytes from file."""
    frames = _make_frames(tmp_path, 2)
    output = tmp_path / "test.gif"
    create_gif(frames, output, resize=(80, 60))

    data = gif_to_bytes(output)
    assert isinstance(data, bytes)
    assert len(data) > 0
    assert data[:6] in (b"GIF87a", b"GIF89a")
