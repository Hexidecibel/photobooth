import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.models.state import (
    TRANSITIONS,
    BoothState,
    CaptureSession,
    InvalidTransitionError,
)

logger = logging.getLogger(__name__)


class StateMachine:
    def __init__(self, broadcast: Callable[..., Awaitable[None]]):
        self._state: BoothState = BoothState.IDLE
        self._session: CaptureSession | None = None
        self._broadcast = broadcast
        self._hooks: dict[str, list[Callable]] = {}

    @property
    def state(self) -> BoothState:
        return self._state

    @property
    def session(self) -> CaptureSession | None:
        return self._session

    def new_session(self, **kwargs: Any) -> CaptureSession:
        self._session = CaptureSession(**kwargs)
        return self._session

    def clear_session(self) -> None:
        self._session = None

    async def transition(self, target: BoothState) -> None:
        if target not in TRANSITIONS[self._state]:
            logger.warning("INVALID transition: %s → %s", self._state, target)
            raise InvalidTransitionError(self._state, target)
        old = self._state
        print(f"[STATE] {old} → {target}")  # Print to stdout for journald
        # Exit current state
        try:
            await self._fire_hook(f"state_{old}_exit")
        except Exception as e:
            logger.error(f"Error in state_{old}_exit: {e}")
        self._state = target
        # Enter new state
        try:
            await self._fire_hook(f"state_{target}_enter")
        except Exception as e:
            logger.error(f"Error in state_{target}_enter: {e}")
        # Broadcast to all WebSocket clients
        await self._broadcast({
            "type": "state_change",
            "state": str(self._state),
            "previous": str(old),
        })
        # Auto-fire _do for capture and processing only
        if self._state in (BoothState.CAPTURE, BoothState.PROCESSING):
            try:
                handler_key = f"state_{self._state}_do"
                result = await self._fire_hook(
                    handler_key, event="enter_complete"
                )
                if result and isinstance(result, BoothState) and result != self._state:
                    await self.transition(result)
            except Exception as e:
                logger.debug(f"Auto-advance from {self._state}: {e}")

    async def trigger(self, event: str, **kwargs: Any) -> None:
        """Handle an external event (button press, touch, timer)."""
        print(f"[EVENT] '{event}' in state {self._state}")
        try:
            handler_key = f"state_{self._state}_do"
            result = await self._fire_hook(handler_key, event=event, **kwargs)
            if result and isinstance(result, BoothState) and result != self._state:
                await self.transition(result)
        except Exception as e:
            logger.error(f"Error handling event '{event}' in {self._state}: {e}")
            await self._broadcast({"type": "error", "message": str(e)})
            # Recovery: return to idle after error
            if self._state != BoothState.IDLE:
                try:
                    await self.transition(BoothState.IDLE)
                except Exception:
                    self._state = BoothState.IDLE
                    await self._broadcast({
                        "type": "state_change",
                        "state": "idle",
                        "previous": None,
                    })

    def register_hook(self, name: str, handler: Callable) -> None:
        """Register a hook handler. Used by plugin manager."""
        self._hooks.setdefault(name, []).append(handler)

    async def _fire_hook(self, name: str, **kwargs: Any) -> Any:
        """Fire all registered handlers for a hook."""
        result = None
        for handler in self._hooks.get(name, []):
            if asyncio.iscoroutinefunction(handler):
                r = await handler(session=self._session, **kwargs)
            else:
                r = await asyncio.to_thread(handler, session=self._session, **kwargs)
            if r is not None:
                result = r
        return result
