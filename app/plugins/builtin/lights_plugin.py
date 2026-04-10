"""Built-in lights plugin -- GPIO LED patterns per state."""

import logging

from app.models.state import BoothState
from app.plugins.hookspec import hookimpl

logger = logging.getLogger(__name__)


class LightsPlugin:
    def __init__(self, config):
        self._config = config
        self._gpio = None

    @hookimpl
    def booth_startup(self, app):
        sm = app.state.state_machine
        # Register enter hooks for LED state changes
        for state in BoothState:
            sm.register_hook(f"state_{state}_enter", self._on_state_enter)

    async def _on_state_enter(self, session, **kwargs):
        """Update LEDs based on current state (if GPIO available)."""
        if not self._gpio:
            return
        # GPIO controller will be set when hardware is initialized

    def set_gpio(self, gpio_controller):
        self._gpio = gpio_controller

    @hookimpl
    def booth_cleanup(self):
        if self._gpio:
            try:
                self._gpio.close()
            except Exception:
                pass
