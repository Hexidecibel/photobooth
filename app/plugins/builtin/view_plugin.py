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
        self._thankyou_task = None

    @hookimpl
    def booth_startup(self, app):
        self._sm = app.state.state_machine
        self._sm.register_hook("state_idle_enter", self._on_idle_enter)
        self._sm.register_hook("state_idle_do", self._on_idle_do)
        self._sm.register_hook("state_choose_do", self._on_choose_do)
        self._sm.register_hook("state_review_do", self._on_review_do)
        self._sm.register_hook("state_print_do", self._on_print_do)
        self._sm.register_hook("state_thankyou_enter", self._on_thankyou_enter)
        self._sm.register_hook("state_thankyou_do", self._on_thankyou_do)

    async def _on_idle_enter(self, session, **kwargs):
        """Clear session and cancel any pending timers."""
        self._sm.clear_session()
        if self._thankyou_task and not self._thankyou_task.done():
            self._thankyou_task.cancel()
            self._thankyou_task = None

    async def _on_idle_do(self, session, event=None, **kwargs):
        if event == "start":
            return BoothState.CHOOSE
        return None

    async def _on_choose_do(self, session, event=None, **kwargs):
        if event == "cancel":
            return BoothState.IDLE
        if event == "select_template":
            # Guest picked a template; store it but stay in choose state
            # (the choose event with template will follow immediately)
            return None
        if event == "choose":
            mode = kwargs.get("mode", "photo")
            template_name = kwargs.get("template", self._config.picture.layout_template)

            # Load template to get slot count = capture count
            try:
                from app.processing.templates import load_template
                tpl = load_template(template_name)
                count = len(tpl.slots)
            except Exception:
                count = int(kwargs.get("count", self._config.picture.capture_count))

            effect = kwargs.get("effect", "none")
            self._sm.new_session(
                mode=mode,
                capture_count=count,
                layout_template=template_name,
            )
            if effect and effect != "none":
                self._sm.session.selected_effect = effect
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
                session.selected_effect = kwargs.get("effect", "none")
            return None
        return None

    async def _on_print_do(self, session, event=None, **kwargs):
        if event == "print_complete" or event == "done":
            return BoothState.THANKYOU
        return None

    async def _on_thankyou_enter(self, session, **kwargs):
        """Start auto-return timer."""
        # Cancel any previous timer
        if self._thankyou_task and not self._thankyou_task.done():
            self._thankyou_task.cancel()
        self._thankyou_task = asyncio.create_task(self._auto_return_to_idle())

    async def _auto_return_to_idle(self):
        await asyncio.sleep(5)
        # Only fire if still in thankyou state
        if self._sm.state == BoothState.THANKYOU:
            await self._broadcast({
                "type": "auto_transition",
                "target": "idle",
            })

    async def _on_thankyou_do(self, session, event=None, **kwargs):
        if event in ("auto_idle", "start", "cancel", "done"):
            return BoothState.IDLE
        return None
