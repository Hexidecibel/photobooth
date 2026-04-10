"""Tests for admin API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.config_schema import AppConfig
from app.services.share_service import ShareService


@pytest.fixture
async def client(tmp_path):
    """Create test client with minimal app state configured."""
    # Set up app state that lifespan would normally provide
    config = AppConfig()
    app.state.config = config
    app.state.camera = None
    app.state.gpio = None
    app.state.printer = None

    sharing_config = config.sharing
    share_svc = ShareService(sharing_config, data_dir=str(tmp_path))
    app.state.share_service = share_svc

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_get_config(client: AsyncClient):
    """GET /api/admin/config returns valid JSON with all sections."""
    response = await client.get("/api/admin/config")
    assert response.status_code == 200
    data = response.json()
    assert "general" in data
    assert "camera" in data
    assert "picture" in data
    assert "printer" in data
    assert "controls" in data
    assert "display" in data
    assert "sharing" in data
    assert "server" in data
    assert "plugin" in data


@pytest.mark.asyncio
async def test_update_config(client: AsyncClient):
    """PATCH /api/admin/config with partial update, verify change persists."""
    response = await client.patch(
        "/api/admin/config",
        json={"general": {"language": "de"}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "updated"

    # Verify the change persists in memory
    response = await client.get("/api/admin/config")
    assert response.status_code == 200
    assert response.json()["general"]["language"] == "de"

    # Restore default
    await client.patch(
        "/api/admin/config",
        json={"general": {"language": "en"}},
    )


@pytest.mark.asyncio
async def test_update_config_invalid(client: AsyncClient):
    """PATCH /api/admin/config with invalid data returns 422."""
    response = await client.patch(
        "/api/admin/config",
        json={"camera": {"rotation": "not-a-number"}},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_system_info(client: AsyncClient):
    """GET /api/admin/system returns platform, camera, printer fields."""
    response = await client.get("/api/admin/system")
    assert response.status_code == 200
    data = response.json()
    assert "platform" in data
    assert "python" in data
    assert "hostname" in data
    assert "camera" in data
    assert "printer" in data
    assert "gpio" in data
    assert "photo_count" in data


@pytest.mark.asyncio
async def test_list_templates(client: AsyncClient):
    """GET /api/admin/templates returns template names."""
    response = await client.get("/api/admin/templates")
    assert response.status_code == 200
    data = response.json()
    assert "templates" in data
    assert isinstance(data["templates"], list)


@pytest.mark.asyncio
async def test_list_effects(client: AsyncClient):
    """GET /api/admin/effects returns effect names."""
    response = await client.get("/api/admin/effects")
    assert response.status_code == 200
    data = response.json()
    assert "effects" in data
    assert isinstance(data["effects"], list)
    assert "none" in data["effects"]
    assert "bw" in data["effects"]
    assert "sepia" in data["effects"]


@pytest.mark.asyncio
async def test_connection_info(client: AsyncClient):
    """GET /api/admin/connection returns booth_url and admin_url."""
    response = await client.get("/api/admin/connection")
    assert response.status_code == 200
    data = response.json()
    assert "booth_url" in data
    assert "admin_url" in data
    assert "ip" in data
    assert "port" in data
    assert "/booth" in data["booth_url"]
    assert "/admin" in data["admin_url"]
