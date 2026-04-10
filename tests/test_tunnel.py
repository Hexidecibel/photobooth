"""Tests for the tunnel service."""

from unittest.mock import MagicMock, patch

import pytest

from app.models.config_schema import NetworkConfig
from app.services.tunnel_service import TunnelService


@pytest.fixture
def disabled_config():
    return NetworkConfig(tunnel_enabled=False, tunnel_command="echo hello")


@pytest.fixture
def enabled_config():
    return NetworkConfig(
        tunnel_enabled=True,
        tunnel_command="/usr/bin/tunnel {port} {name} --bg",
        tunnel_name="mybooth",
        tunnel_url_pattern="https://{name}.tunnel.example.com",
    )


@pytest.fixture
def enabled_no_command():
    return NetworkConfig(tunnel_enabled=True, tunnel_command="")


@pytest.mark.asyncio
async def test_tunnel_disabled_returns_none(disabled_config):
    """When tunnel_enabled is False, start() returns None immediately."""
    svc = TunnelService(disabled_config, port=8000)
    result = await svc.start()
    assert result is None
    assert svc.public_url is None
    assert svc.is_running is False


@pytest.mark.asyncio
async def test_tunnel_no_command_returns_none(enabled_no_command):
    """When tunnel_enabled but command is empty, start() returns None."""
    svc = TunnelService(enabled_no_command, port=8000)
    result = await svc.start()
    assert result is None
    assert svc.public_url is None


@pytest.mark.asyncio
async def test_tunnel_url_pattern(enabled_config):
    """Verify URL is correctly formatted from pattern + name."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # Still running

    with patch("app.services.tunnel_service.subprocess.Popen", return_value=mock_proc):
        svc = TunnelService(enabled_config, port=9000)
        result = await svc.start()

    assert result == "https://mybooth.tunnel.example.com"
    assert svc.public_url == "https://mybooth.tunnel.example.com"


@pytest.mark.asyncio
async def test_tunnel_service_properties(enabled_config):
    """is_running is False when not started, public_url is None."""
    svc = TunnelService(enabled_config, port=8000)
    assert svc.is_running is False
    assert svc.public_url is None


@pytest.mark.asyncio
async def test_tunnel_stop(enabled_config):
    """stop() terminates the process and clears state."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.wait.return_value = 0

    with patch("app.services.tunnel_service.subprocess.Popen", return_value=mock_proc):
        svc = TunnelService(enabled_config, port=9000)
        await svc.start()

    await svc.stop()
    mock_proc.terminate.assert_called_once()
    assert svc.public_url is None


@pytest.mark.asyncio
async def test_tunnel_process_exits_immediately(enabled_config):
    """If the process exits immediately, start() returns None."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 1  # Already exited
    mock_proc.stderr = MagicMock()
    mock_proc.stderr.read.return_value = b"connection refused"

    with patch("app.services.tunnel_service.subprocess.Popen", return_value=mock_proc):
        svc = TunnelService(enabled_config, port=9000)
        result = await svc.start()

    assert result is None
    assert svc.public_url is None
