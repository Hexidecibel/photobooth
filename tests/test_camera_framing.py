"""Tests for camera zoom, crop, and framing controls."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.camera.base import CameraBase, CropRegion
from app.main import app
from app.models.config_schema import AppConfig
from app.services.share_service import ShareService

# ── CropRegion unit tests ────────────────────────────────────────

def test_crop_region_defaults():
    """Default CropRegion represents the full frame."""
    r = CropRegion()
    assert r.x == 0.0
    assert r.y == 0.0
    assert r.width == 1.0
    assert r.height == 1.0


def test_crop_region_custom():
    """CropRegion stores custom values."""
    r = CropRegion(0.25, 0.25, 0.5, 0.5)
    assert r.x == 0.25
    assert r.y == 0.25
    assert r.width == 0.5
    assert r.height == 0.5


# ── CameraBase zoom/crop tests ──────────────────────────────────

class DummyCamera(CameraBase):
    """Minimal concrete camera for testing base class methods."""

    async def start_preview(self, resolution=(1920, 1080)):
        pass

    async def stop_preview(self):
        pass

    async def stream_mjpeg(self):
        yield b""

    async def capture_still(self, path):
        return path

    async def capture_sequence(self, count, interval_ms, output_dir):
        return []

    async def close(self):
        pass

    @classmethod
    def detect(cls):
        return True


def test_set_zoom_center_crop():
    """Zoom 2.0 produces a centered 50% crop."""
    cam = DummyCamera()
    cam.set_zoom(2.0)
    c = cam.crop
    assert abs(c.x - 0.25) < 1e-9
    assert abs(c.y - 0.25) < 1e-9
    assert abs(c.width - 0.5) < 1e-9
    assert abs(c.height - 0.5) < 1e-9


def test_set_zoom_no_zoom():
    """Zoom 1.0 produces full frame."""
    cam = DummyCamera()
    cam.set_zoom(1.0)
    c = cam.crop
    assert c.x == 0.0
    assert c.y == 0.0
    assert c.width == 1.0
    assert c.height == 1.0


def test_set_zoom_below_one():
    """Zoom below 1.0 resets to full frame."""
    cam = DummyCamera()
    cam.set_zoom(2.0)  # Set a crop first
    cam.set_zoom(0.5)  # Then reset
    c = cam.crop
    assert c.width == 1.0
    assert c.height == 1.0


def test_set_zoom_3x():
    """Zoom 3.0 produces correct centered crop."""
    cam = DummyCamera()
    cam.set_zoom(3.0)
    c = cam.crop
    expected_size = 1.0 / 3.0
    expected_offset = (1.0 - expected_size) / 2
    assert abs(c.width - expected_size) < 1e-9
    assert abs(c.height - expected_size) < 1e-9
    assert abs(c.x - expected_offset) < 1e-9
    assert abs(c.y - expected_offset) < 1e-9


def test_set_crop_manual():
    """set_crop stores the given region."""
    cam = DummyCamera()
    r = CropRegion(0.1, 0.2, 0.6, 0.7)
    cam.set_crop(r)
    assert cam.crop.x == 0.1
    assert cam.crop.y == 0.2
    assert cam.crop.width == 0.6
    assert cam.crop.height == 0.7


def test_crop_default_without_set():
    """Accessing crop before set_crop returns full frame."""
    cam = DummyCamera()
    c = cam.crop
    assert c.width == 1.0
    assert c.height == 1.0


# ── API endpoint tests ──────────────────────────────────────────

@pytest.fixture
async def client(tmp_path):
    """Create test client with minimal app state."""
    config = AppConfig()
    app.state.config = config
    app.state.camera = None
    app.state.gpio = None
    app.state.printer = None

    share_svc = ShareService(config.sharing, data_dir=str(tmp_path))
    app.state.share_service = share_svc

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_camera_framing_endpoint(client: AsyncClient):
    """GET /api/admin/camera/framing returns current framing values."""
    response = await client.get("/api/admin/camera/framing")
    assert response.status_code == 200
    data = response.json()
    assert "crop_x" in data
    assert "crop_y" in data
    assert "crop_width" in data
    assert "crop_height" in data
    assert "zoom" in data
    assert "mirror_preview" in data
    assert "mirror_capture" in data
    # Check defaults
    assert data["zoom"] == 1.0
    assert data["crop_width"] == 1.0
    assert data["mirror_preview"] is True
    assert data["mirror_capture"] is False


@pytest.mark.asyncio
async def test_update_camera_framing(client: AsyncClient):
    """PATCH /api/admin/camera/framing updates and persists."""
    response = await client.patch(
        "/api/admin/camera/framing",
        json={"zoom": 2.0, "mirror_preview": False},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "updated"

    # Verify persisted
    response = await client.get("/api/admin/camera/framing")
    data = response.json()
    assert data["zoom"] == 2.0
    assert data["mirror_preview"] is False

    # Reset for other tests
    await client.patch(
        "/api/admin/camera/framing",
        json={"zoom": 1.0, "mirror_preview": True},
    )


@pytest.mark.asyncio
async def test_update_camera_framing_crop(client: AsyncClient):
    """PATCH with crop values updates correctly."""
    response = await client.patch(
        "/api/admin/camera/framing",
        json={"crop_x": 0.1, "crop_y": 0.2, "crop_width": 0.8, "crop_height": 0.7},
    )
    assert response.status_code == 200

    response = await client.get("/api/admin/camera/framing")
    data = response.json()
    assert abs(data["crop_x"] - 0.1) < 1e-9
    assert abs(data["crop_y"] - 0.2) < 1e-9
    assert abs(data["crop_width"] - 0.8) < 1e-9
    assert abs(data["crop_height"] - 0.7) < 1e-9

    # Reset
    await client.patch(
        "/api/admin/camera/framing",
        json={"crop_x": 0.0, "crop_y": 0.0, "crop_width": 1.0, "crop_height": 1.0},
    )


# ── Config schema tests ─────────────────────────────────────────

def test_camera_config_has_framing_fields():
    """CameraConfig includes all framing fields with correct defaults."""
    from app.models.config_schema import CameraConfig

    config = CameraConfig()
    assert config.crop_x == 0.0
    assert config.crop_y == 0.0
    assert config.crop_width == 1.0
    assert config.crop_height == 1.0
    assert config.zoom == 1.0
    assert config.mirror_preview is True
    assert config.mirror_capture is False
