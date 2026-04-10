import pytest

from app.models.state import BoothState, CaptureSession, InvalidTransitionError
from app.services.state_machine import StateMachine


@pytest.fixture
def messages() -> list[dict]:
    return []


@pytest.fixture
def sm(messages: list[dict]) -> StateMachine:
    async def broadcast(msg: dict) -> None:
        messages.append(msg)

    return StateMachine(broadcast=broadcast)


@pytest.mark.asyncio
async def test_initial_state_is_idle(sm: StateMachine):
    assert sm.state == BoothState.IDLE


@pytest.mark.asyncio
async def test_valid_transition(sm: StateMachine):
    await sm.transition(BoothState.CHOOSE)
    assert sm.state == BoothState.CHOOSE


@pytest.mark.asyncio
async def test_invalid_transition(sm: StateMachine):
    with pytest.raises(InvalidTransitionError) as exc_info:
        await sm.transition(BoothState.CAPTURE)
    assert exc_info.value.current == BoothState.IDLE
    assert exc_info.value.target == BoothState.CAPTURE


@pytest.mark.asyncio
async def test_full_photo_flow(sm: StateMachine):
    flow = [
        BoothState.CHOOSE,
        BoothState.PREVIEW,
        BoothState.CAPTURE,
        BoothState.PROCESSING,
        BoothState.REVIEW,
        BoothState.PRINT,
        BoothState.THANKYOU,
        BoothState.IDLE,
    ]
    for target in flow:
        await sm.transition(target)
    assert sm.state == BoothState.IDLE


@pytest.mark.asyncio
async def test_retake_from_review(sm: StateMachine):
    for s in [BoothState.CHOOSE, BoothState.PREVIEW, BoothState.CAPTURE,
              BoothState.PROCESSING, BoothState.REVIEW]:
        await sm.transition(s)
    await sm.transition(BoothState.PREVIEW)
    assert sm.state == BoothState.PREVIEW


@pytest.mark.asyncio
async def test_cancel_from_choose(sm: StateMachine):
    await sm.transition(BoothState.CHOOSE)
    await sm.transition(BoothState.IDLE)
    assert sm.state == BoothState.IDLE


@pytest.mark.asyncio
async def test_multi_shot_loop(sm: StateMachine):
    await sm.transition(BoothState.CHOOSE)
    await sm.transition(BoothState.PREVIEW)
    await sm.transition(BoothState.CAPTURE)
    # Loop back for another shot
    await sm.transition(BoothState.PREVIEW)
    await sm.transition(BoothState.CAPTURE)
    # Done capturing
    await sm.transition(BoothState.PROCESSING)
    assert sm.state == BoothState.PROCESSING


@pytest.mark.asyncio
async def test_broadcast_called_on_transition(sm: StateMachine, messages: list[dict]):
    await sm.transition(BoothState.CHOOSE)
    assert len(messages) == 1
    msg = messages[0]
    assert msg["type"] == "state_change"
    assert msg["state"] == "choose"
    assert msg["previous"] == "idle"


@pytest.mark.asyncio
async def test_session_lifecycle(sm: StateMachine):
    assert sm.session is None
    session = sm.new_session(mode="gif", capture_count=3)
    assert sm.session is session
    assert isinstance(session, CaptureSession)
    assert session.mode == "gif"
    assert session.capture_count == 3
    assert len(session.id) == 12
    sm.clear_session()
    assert sm.session is None


@pytest.mark.asyncio
async def test_trigger_fires_hooks(sm: StateMachine):
    calls: list[dict] = []

    async def idle_handler(session=None, event=None, **kwargs):
        calls.append({"event": event, "session": session})
        return BoothState.CHOOSE

    sm.register_hook("state_idle_do", idle_handler)
    await sm.trigger("button_press")
    assert len(calls) == 1
    assert calls[0]["event"] == "button_press"
    # trigger should have auto-transitioned to CHOOSE
    assert sm.state == BoothState.CHOOSE
