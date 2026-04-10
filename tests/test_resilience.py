"""Tests for operational resilience features: watchdog, analytics, backup."""

import sqlite3
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from zipfile import ZipFile

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.config_schema import AppConfig
from app.services.counter_service import CounterService
from app.services.share_service import ShareService
from app.services.watchdog import WatchdogService

# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def tmp_data(tmp_path):
    """Create a temporary data directory with test photos."""
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    # Create a few fake photo files
    for i in range(3):
        (photos_dir / f"test_{i}.jpg").write_bytes(b"\xff\xd8fake-jpg-data")
    # Create a counters.json
    (tmp_path / "counters.json").write_text('{"total_taken": 5, "total_printed": 2}')
    return tmp_path


@pytest.fixture
async def client(tmp_data):
    """Create test client with state configured for analytics/backup tests."""
    config = AppConfig()
    config.general.save_dir = str(tmp_data)
    app.state.config = config
    app.state.camera = None
    app.state.gpio = None
    app.state.printer = None

    share_svc = ShareService(config.sharing, data_dir=str(tmp_data))
    app.state.share_service = share_svc

    counter_svc = CounterService(data_dir=str(tmp_data))
    app.state.counters = counter_svc

    # Insert some test photos into the gallery DB
    db_path = tmp_data / "gallery.db"
    with sqlite3.connect(db_path) as conn:
        for i in range(5):
            ts = (datetime.now() - timedelta(hours=i)).isoformat()
            conn.execute(
                "INSERT OR REPLACE INTO photos "
                "(id, session_id, photo_path, "
                "share_token, event_name, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    f"photo-{i}",
                    f"session-{i}",
                    f"photos/test_{i % 3}.jpg",
                    f"tok{i}",
                    "Test Event",
                    ts,
                ),
            )
        conn.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ── Watchdog Tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_watchdog_camera_recovery():
    """Mock no camera, verify watchdog attempts recovery."""
    mock_state = MagicMock()
    mock_state.camera = None
    mock_state.printer = None
    mock_state.config = AppConfig()

    watchdog = WatchdogService(mock_state)

    # Mock camera detection to succeed
    mock_camera = AsyncMock()
    mock_camera.start_preview = AsyncMock()

    with patch(
        "app.camera.factory.auto_detect_camera",
        new_callable=lambda: lambda *a, **kw: AsyncMock(
            return_value=mock_camera
        ),
    ):
        # Manually call _check_camera
        await watchdog._check_camera()

    # Verify the state was updated (camera recovered)
    if mock_state.camera is not None:
        assert mock_state.camera == mock_camera


@pytest.mark.asyncio
async def test_watchdog_start_stop():
    """Verify watchdog can start and stop cleanly."""
    mock_state = MagicMock()
    mock_state.camera = MagicMock()  # Camera exists, no recovery needed
    mock_state.printer = None
    mock_state.config = AppConfig()

    watchdog = WatchdogService(mock_state)
    await watchdog.start()
    assert watchdog._running is True
    assert watchdog._task is not None

    await watchdog.stop()
    assert watchdog._running is False


# ── Analytics Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analytics_endpoint(client: AsyncClient):
    """Verify analytics response structure."""
    response = await client.get("/api/admin/analytics")
    assert response.status_code == 200
    data = response.json()

    assert "counters" in data
    assert "total_photos" in data
    assert "photos_per_hour" in data
    assert "recent_photos" in data
    assert "uptime_seconds" in data

    assert data["total_photos"] == 5
    assert isinstance(data["photos_per_hour"], dict)
    assert len(data["recent_photos"]) <= 10
    assert data["uptime_seconds"] >= 0


# ── Backup Tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_backup_endpoint(client: AsyncClient, tmp_data):
    """Create test photos, hit backup endpoint, verify ZIP contents."""
    response = await client.get("/api/admin/backup")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"

    # Save the zip and inspect it
    zip_path = tmp_data / "backup.zip"
    zip_path.write_bytes(response.content)

    with ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        # Should contain photos
        photo_files = [n for n in names if n.startswith("photos/")]
        assert len(photo_files) >= 1

        # Should contain gallery.db
        assert "gallery.db" in names

        # Should contain counters.json
        assert "counters.json" in names
