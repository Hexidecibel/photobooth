"""WebSocket endpoint for booth state synchronization."""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.state_machine import StateMachine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["booth"])

# Connected WebSocket clients
_clients: set[WebSocket] = set()


async def broadcast(message: dict) -> None:
    """Send a message to all connected WebSocket clients."""
    disconnected = set()
    for ws in _clients:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.add(ws)
    _clients.difference_update(disconnected)


@router.websocket("/ws/booth")
async def booth_ws(ws: WebSocket):
    """WebSocket endpoint for real-time booth state updates."""
    await ws.accept()
    _clients.add(ws)

    # Get state machine from app state (can't use Depends in WebSocket easily)
    sm: StateMachine = ws.app.state.state_machine

    # Build sound config for the client
    sound_config = {}
    if hasattr(ws.app.state, "config") and hasattr(ws.app.state.config, "sound"):
        sound_config = ws.app.state.config.sound.model_dump()

    # Build language from config
    language = "en"
    if hasattr(ws.app.state, "config") and hasattr(ws.app.state.config, "general"):
        language = ws.app.state.config.general.language or "en"

    # Build guest_picks_template flag from config
    guest_picks_template = False
    if hasattr(ws.app.state, "config") and hasattr(ws.app.state.config, "picture"):
        guest_picks_template = ws.app.state.config.picture.guest_picks_template

    # Check printer availability
    printer = getattr(ws.app.state, "printer", None)
    has_printer = printer is not None and printer.is_available if printer else False

    # Send current state on connect
    await ws.send_json({
        "type": "state_change",
        "state": str(sm.state),
        "previous": None,
        "sound_config": sound_config,
        "language": language,
        "config": {
            "guest_picks_template": guest_picks_template,
            "has_printer": has_printer,
        },
    })

    try:
        while True:
            data = await ws.receive_json()
            action = data.get("action")
            if not action:
                continue

            try:
                await sm.trigger(
                    action, **{k: v for k, v in data.items() if k != "action"}
                )
            except Exception as e:
                await ws.send_json({"type": "error", "message": str(e)})
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(ws)
