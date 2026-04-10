"""Tests for the camera streaming endpoint."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.camera.base import CameraBase
from app.main import app


class MockCamera(CameraBase):
    """Mock camera for testing."""

    async def start_preview(self, resolution: tuple[int, int] = (1920, 1080)) -> None:
        pass

    async def stop_preview(self) -> None:
        pass

    async def stream_mjpeg(self) -> AsyncIterator[bytes]:
        yield b"\xff\xd8\xff\xe0test_frame"

    async def capture_still(self, path: Path) -> Path:
        return path

    async def capture_sequence(
        self, count: int, interval_ms: int, output_dir: Path
    ) -> list[Path]:
        return []

    async def close(self) -> None:
        pass

    @classmethod
    def detect(cls) -> bool:
        return True


@pytest.fixture
async def client_with_camera():
    """Client with a mock camera installed."""
    original_camera = getattr(app.state, "camera", None)
    app.state.camera = MockCamera()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.state.camera = original_camera


@pytest.fixture
async def client_no_camera():
    """Client with no camera available."""
    original_camera = getattr(app.state, "camera", None)
    app.state.camera = None
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.state.camera = original_camera


@pytest.mark.asyncio
async def test_camera_stream_endpoint_exists(client_with_camera: AsyncClient):
    """GET /api/camera/stream returns 200 with correct content-type."""
    response = await client_with_camera.get("/api/camera/stream")
    assert response.status_code == 200
    assert "multipart/x-mixed-replace" in response.headers["content-type"]
    assert b"test_frame" in response.content


@pytest.mark.asyncio
async def test_camera_stream_no_camera(client_no_camera: AsyncClient):
    """When app.state.camera is None, returns 503."""
    response = await client_no_camera.get("/api/camera/stream")
    assert response.status_code == 503
    assert "No camera available" in response.json()["detail"]
