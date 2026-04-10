import tempfile
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.models.config_schema import SharingConfig
from app.models.state import CaptureSession
from app.services.share_service import ShareService


@pytest.fixture
def share_service(tmp_path):
    config = SharingConfig(
        enabled=True,
        base_url="http://localhost:8000",
        qr_size=200,
        event_name="Test Event",
    )
    return ShareService(config, data_dir=str(tmp_path))


@pytest.fixture
def sample_session(tmp_path):
    photo = tmp_path / "test_photo.jpg"
    photo.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)  # fake JPEG
    session = CaptureSession()
    session.composite_path = photo
    return session


def test_share_service_create_token(share_service, sample_session):
    token = share_service.create_share(sample_session)
    assert isinstance(token, str)
    assert len(token) == 8
    assert sample_session.share_token == token


def test_share_service_get_by_token(share_service, sample_session):
    token = share_service.create_share(sample_session)
    photo = share_service.get_by_token(token)
    assert photo is not None
    assert photo["id"] == sample_session.id
    assert photo["share_token"] == token
    assert photo["event_name"] == "Test Event"


def test_share_service_get_by_token_not_found(share_service):
    result = share_service.get_by_token("nonexistent")
    assert result is None


def test_share_service_list_photos(share_service):
    sessions = []
    for _ in range(3):
        session = CaptureSession()
        session.composite_path = Path("/tmp/fake.jpg")
        share_service.create_share(session)
        sessions.append(session)

    photos = share_service.list_photos()
    assert len(photos) == 3


def test_share_service_delete_photo(share_service, sample_session):
    share_service.create_share(sample_session)
    assert share_service.get_by_id(sample_session.id) is not None

    result = share_service.delete_photo(sample_session.id)
    assert result is True
    assert share_service.get_by_id(sample_session.id) is None


def test_share_service_delete_not_found(share_service):
    result = share_service.delete_photo("nonexistent")
    assert result is False


def test_share_service_qr_generation(share_service):
    qr_bytes = share_service.generate_qr_png("http://example.com/share/abc123")
    # If qrcode is installed, we get PNG bytes
    if qr_bytes:
        assert qr_bytes[:4] == b"\x89PNG"
        assert len(qr_bytes) > 100


def test_share_service_get_share_url(share_service):
    url = share_service.get_share_url("abc123")
    assert url == "http://localhost:8000/share/abc123"


def test_share_service_get_share_url_no_base():
    config = SharingConfig(base_url="")
    svc = ShareService(config, data_dir=tempfile.mkdtemp())
    url = svc.get_share_url("abc123")
    assert url == "/share/abc123"


# --- API endpoint tests ---


@pytest.fixture
async def client(tmp_path):
    from app.main import app

    # Set up share_service on app.state so endpoints work without full lifespan
    config = SharingConfig(event_name="Test Event")
    app.state.share_service = ShareService(config, data_dir=str(tmp_path))

    from app.models.config_schema import AppConfig

    app.state.config = AppConfig()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_share_endpoint_not_found(client: AsyncClient):
    response = await client.get("/api/share/invalid_token_xyz")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_gallery_list_empty(client: AsyncClient):
    response = await client.get("/api/gallery/")
    assert response.status_code == 200
    data = response.json()
    assert "photos" in data
    assert isinstance(data["photos"], list)
