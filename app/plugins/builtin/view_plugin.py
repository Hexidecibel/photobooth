"""Built-in view plugin -- handles UI state logic and timeouts."""

import asyncio
import logging

from app.models.state import BoothState
from app.plugins.hookspec import hookimpl

logger = logging.getLogger(__name__)


class ViewPlugin:
    def __init__(self, config, broadcast):
        self._config = config
        self._broadcast = broadcast

    @hookimpl
    def booth_startup(self, app):
        self._sm = app.state.state_machine
        self._sm.register_hook("state_idle_do", self._on_idle_do)
        self._sm.register_hook("state_choose_do", self._on_choose_do)
        self._sm.register_hook("state_review_do", self._on_review_do)
        self._sm.register_hook("state_print_do", self._on_print_do)
        self._sm.register_hook("state_thankyou_enter", self._on_thankyou_enter)
        self._sm.register_hook("state_thankyou_do", self._on_thankyou_do)

    async def _on_idle_do(self, session, event=None, **kwargs):
        if event == "start":
            return BoothState.CHOOSE
        return None

    async def _on_choose_do(self, session, event=None, **kwargs):
        if event == "cancel":
            return BoothState.IDLE
        if event == "choose":
            # Create a new capture session with the chosen mode/count
            mode = kwargs.get("mode", "photo")
            count = kwargs.get("count", self._config.picture.capture_count)
            self._sm.new_session(mode=mode, capture_count=int(count))
            return BoothState.PREVIEW
        return None

    async def _on_review_do(self, session, event=None, **kwargs):
        if event == "retake":
            if session:
                session.captures.clear()
                session.composite_path = None
            return BoothState.PREVIEW
        if event == "print":
            return BoothState.PRINT
        if event == "done":
            return BoothState.THANKYOU
        if event == "select_effect":
            if session:
                session.selected_effect = kwargs.get("effect")
            return None  # Stay in review
        return None

    async def _on_print_do(self, session, event=None, **kwargs):
        if event == "print_complete" or event == "done":
            return BoothState.THANKYOU
        return None

    async def _on_thankyou_enter(self, session, **kwargs):
        """Start auto-return timer."""
        asyncio.create_task(self._auto_return_to_idle())

    async def _auto_return_to_idle(self):
        await asyncio.sleep(5)
        await self._broadcast({
            "type": "auto_transition",
            "target": "idle",
        })

    async def _on_thankyou_do(self, session, event=None, **kwargs):
        if event == "auto_idle" or event == "start":
            return BoothState.IDLE
        return None
