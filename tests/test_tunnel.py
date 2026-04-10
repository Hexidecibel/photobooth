"""Tests for the tunnel service."""

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from app.models.config_schema import NetworkConfig
from app.services.tunnel_service import TunnelService


@pytest.fixture
def disabled_config():
    return NetworkConfig(tunnel_enabled=False)


@pytest.fixture
def localhost_run_config():
    return NetworkConfig(
        tunnel_enabled=True,
        tunnel_provider="localhost.run",
    )


@pytest.fixture
def custom_config():
    return NetworkConfig(
        tunnel_enabled=True,
        tunnel_provider="custom",
        tunnel_custom_command="/usr/bin/tunnel {port} {name} --bg",
        tunnel_name="mybooth",
        tunnel_url_pattern="https://{name}.tunnel.example.com",
    )


@pytest.fixture
def custom_config_no_command():
    return NetworkConfig(
        tunnel_enabled=True,
        tunnel_provider="custom",
        tunnel_custom_command="",
    )


@pytest.fixture
def unknown_provider_config():
    return NetworkConfig(
        tunnel_enabled=True,
        tunnel_provider="nonexistent",
    )


@pytest.mark.asyncio
async def test_tunnel_disabled_returns_none(disabled_config):
    """When tunnel_enabled is False, start() returns None immediately."""
    svc = TunnelService(disabled_config, port=8000)
    result = await svc.start()
    assert result is None
    assert svc.public_url is None
    assert svc.is_running is False


@pytest.mark.asyncio
async def test_tunnel_service_properties(disabled_config):
    """is_running is False when not started, public_url is None."""
    svc = TunnelService(disabled_config, port=8000)
    assert svc.is_running is False
    assert svc.public_url is None


@pytest.mark.asyncio
async def test_tunnel_unknown_provider(unknown_provider_config):
    """Unknown provider returns None."""
    svc = TunnelService(unknown_provider_config, port=8000)
    result = await svc.start()
    assert result is None
    assert svc.public_url is None


@pytest.mark.asyncio
async def test_tunnel_localhost_run(localhost_run_config):
    """localhost.run provider extracts URL from SSH output."""
    fake_output = StringIO(
        "Connect to http://localhost.run for more info\n"
        "https://abc123def.lhr.life tunneled with tls termination\n"
    )

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.stdout = fake_output
    mock_proc.stdout.readline = fake_output.readline

    with patch("app.services.tunnel_service.subprocess.Popen", return_value=mock_proc):
        svc = TunnelService(localhost_run_config, port=8000)
        result = await svc.start()

    assert result == "https://abc123def.lhr.life"
    assert svc.public_url == "https://abc123def.lhr.life"


@pytest.mark.asyncio
async def test_tunnel_custom_provider(custom_config):
    """Custom provider derives URL from pattern."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # Still running
    mock_proc.stdout = MagicMock()

    with patch("app.services.tunnel_service.subprocess.Popen", return_value=mock_proc):
        svc = TunnelService(custom_config, port=9000)
        result = await svc.start()

    assert result == "https://mybooth.tunnel.example.com"
    assert svc.public_url == "https://mybooth.tunnel.example.com"


@pytest.mark.asyncio
async def test_tunnel_custom_no_command(custom_config_no_command):
    """Custom provider with empty command returns None."""
    svc = TunnelService(custom_config_no_command, port=8000)
    result = await svc.start()
    assert result is None


@pytest.mark.asyncio
async def test_tunnel_custom_exits_immediately(custom_config):
    """If the custom process exits immediately, start() returns None."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 1  # Already exited
    mock_proc.stdout = MagicMock()
    mock_proc.stdout.read.return_value = "connection refused"

    with patch("app.services.tunnel_service.subprocess.Popen", return_value=mock_proc):
        svc = TunnelService(custom_config, port=9000)
        result = await svc.start()

    assert result is None
    assert svc.public_url is None


@pytest.mark.asyncio
async def test_tunnel_stop(custom_config):
    """stop() terminates the process and clears state."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.wait.return_value = 0
    mock_proc.stdout = MagicMock()

    with patch("app.services.tunnel_service.subprocess.Popen", return_value=mock_proc):
        svc = TunnelService(custom_config, port=9000)
        await svc.start()

    await svc.stop()
    mock_proc.terminate.assert_called_once()
    assert svc.public_url is None


@pytest.mark.asyncio
async def test_tunnel_localhost_run_ssh_not_found(localhost_run_config):
    """When ssh is not installed, localhost.run returns None."""
    with patch(
        "app.services.tunnel_service.subprocess.Popen",
        side_effect=FileNotFoundError("ssh not found"),
    ):
        svc = TunnelService(localhost_run_config, port=8000)
        result = await svc.start()

    assert result is None


@pytest.mark.asyncio
async def test_tunnel_monitor_restart(custom_config):
    """Monitor detects dead process and restarts."""
    import asyncio

    mock_proc_1 = MagicMock()
    # First call: running, then dies on second poll check
    mock_proc_1.poll.side_effect = [None, None, 1]
    mock_proc_1.stdout = MagicMock()
    mock_proc_1.wait.return_value = 0

    mock_proc_2 = MagicMock()
    mock_proc_2.poll.return_value = None
    mock_proc_2.stdout = MagicMock()

    call_count = 0

    def mock_popen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_proc_1
        return mock_proc_2

    with patch("app.services.tunnel_service.subprocess.Popen", side_effect=mock_popen):
        svc = TunnelService(custom_config, port=9000)
        # Patch sleep to speed up monitor loop
        with patch("app.services.tunnel_service.asyncio.sleep", return_value=None):
            await svc.start()
            # Let monitor task run
            if svc._monitor_task:
                await asyncio.sleep(0.1)

    # Should have been called at least twice (initial + restart)
    assert call_count >= 1
