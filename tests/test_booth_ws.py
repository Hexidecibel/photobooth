"""Tests for the WebSocket booth endpoint."""

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.models.state import BoothState
from app.routers.booth import _clients


@pytest.fixture(autouse=True)
def clear_clients():
    """Ensure the client set is clean between tests."""
    _clients.clear()
    yield
    _clients.clear()


def test_ws_connect_receives_state():
    """Connect to /ws/booth and receive initial state_change message."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/booth") as ws:
            data = ws.receive_json()
            assert data["type"] == "state_change"
            assert data["state"] == "idle"
            assert data["previous"] is None


def test_ws_send_action():
    """Send an action and verify state machine receives trigger."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/booth") as ws:
            # Consume initial state
            ws.receive_json()

            # Register a hook so "start" triggers a transition
            sm = app.state.state_machine

            async def idle_handler(session=None, event=None, **kwargs):
                if event == "start":
                    return BoothState.CHOOSE

            sm.register_hook("state_idle_do", idle_handler)

            try:
                ws.send_json({"action": "start"})
                # Should receive state_change from the transition broadcast
                data = ws.receive_json()
                assert data["type"] == "state_change"
                assert data["state"] == "choose"
                assert data["previous"] == "idle"
            finally:
                # Reset state machine for other tests
                sm._state = BoothState.IDLE
                sm._hooks.pop("state_idle_do", None)


def test_ws_broadcast():
    """Connect two clients, trigger transition, both receive state_change."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/booth") as ws1:
            with client.websocket_connect("/ws/booth") as ws2:
                # Consume initial state for both
                ws1.receive_json()
                ws2.receive_json()

                sm = app.state.state_machine

                async def idle_handler(session=None, event=None, **kwargs):
                    if event == "go":
                        return BoothState.CHOOSE

                sm.register_hook("state_idle_do", idle_handler)

                try:
                    ws1.send_json({"action": "go"})
                    # Both should receive the broadcast
                    data1 = ws1.receive_json()
                    data2 = ws2.receive_json()
                    assert data1["type"] == "state_change"
                    assert data1["state"] == "choose"
                    assert data2["type"] == "state_change"
                    assert data2["state"] == "choose"
                finally:
                    sm._state = BoothState.IDLE
                    sm._hooks.pop("state_idle_do", None)


def test_ws_invalid_action_returns_error():
    """Send an action that causes an error, receive error message."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/booth") as ws:
            # Consume initial state
            ws.receive_json()

            sm = app.state.state_machine

            async def bad_handler(session=None, event=None, **kwargs):
                raise ValueError("Something went wrong")

            sm.register_hook("state_idle_do", bad_handler)

            try:
                ws.send_json({"action": "bad"})
                data = ws.receive_json()
                assert data["type"] == "error"
                assert "Something went wrong" in data["message"]
            finally:
                sm._hooks.pop("state_idle_do", None)
