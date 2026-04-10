"""Tests for gallery thumbnail endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.models.config_schema import AppConfig, SharingConfig
from app.models.state import CaptureSession
from app.services.counter_service import CounterService
from app.services.share_service import ShareService


@pytest.fixture
async def client_with_photo(tmp_path):
    """Create a test client with a photo in the gallery."""
    from app.main import app

    config = SharingConfig(event_name="Test Event")
    share_svc = ShareService(config, data_dir=str(tmp_path))
    app.state.share_service = share_svc
    app.state.config = AppConfig()
    app.state.counters = CounterService(data_dir=str(tmp_path))

    # Create a real JPEG-like image using PIL
    photo_path = tmp_path / "test_photo.jpg"
    try:
        from PIL import Image

        img = Image.new("RGB", (800, 600), color=(100, 150, 200))
        img.save(str(photo_path), format="JPEG")
    except ImportError:
        # Fallback: write minimal JPEG bytes
        photo_path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

    session = CaptureSession()
    session.composite_path = photo_path
    share_svc.create_share(session)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac, session.id


@pytest.mark.asyncio
async def test_gallery_thumbnail_endpoint(client_with_photo):
    """Thumbnail endpoint returns resized image."""
    client, photo_id = client_with_photo
    response = await client.get(f"/api/gallery/{photo_id}/thumbnail")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert len(response.content) > 0


@pytest.mark.asyncio
async def test_gallery_thumbnail_not_found(client_with_photo):
    """Thumbnail for non-existent photo returns 404."""
    client, _ = client_with_photo
    response = await client.get("/api/gallery/nonexistent/thumbnail")
    assert response.status_code == 404
