"""GPIOController -- manages physical buttons and LEDs via gpiozero.

Handles non-Pi environments gracefully by catching ImportError on gpiozero.

Button behaviour is state-aware: each button triggers a different action
depending on the current BoothState (see ``_on_button``).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.models.config_schema import ControlsConfig
from app.models.state import BoothState

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from app.services.state_machine import StateMachine

logger = logging.getLogger(__name__)


class GPIOController:
    def __init__(
        self,
        config: ControlsConfig,
        state_machine: StateMachine,
        broadcast: Callable[..., Awaitable[None]],
    ):
        self._config = config
        self._sm = state_machine
        self._broadcast = broadcast
        self._capture_btn = None
        self._print_btn = None
        self._capture_led = None
        self._print_led = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._setup()

    def _setup(self):
        try:
            from gpiozero import LED, Button

            self._capture_btn = Button(
                self._config.capture_button_pin,
                bounce_time=self._config.debounce_ms / 1000,
            )
            self._print_btn = Button(
                self._config.print_button_pin,
                bounce_time=self._config.debounce_ms / 1000,
            )
            self._capture_led = LED(self._config.capture_led_pin)
            self._print_led = LED(self._config.print_led_pin)

            # Button callbacks bridge sync gpiozero -> async state machine
            self._capture_btn.when_pressed = self._handle_capture
            self._print_btn.when_pressed = self._handle_print

            print(f"[GPIO] Initialized: capture_btn=pin{self._config.capture_button_pin}, print_btn=pin{self._config.print_button_pin}, capture_led=pin{self._config.capture_led_pin}, print_led=pin{self._config.print_led_pin}")
        except (ImportError, RuntimeError) as e:
            print(f"[GPIO] NOT available: {e}")

    # -- sync callbacks dispatched from gpiozero thread ------------------

    def _handle_capture(self):
        """Left/capture button pressed."""
        print("[GPIO] Raw capture button callback fired")
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._on_button("capture"), self._loop
            )

    def _handle_print(self):
        """Right/print button pressed."""
        print("[GPIO] Raw print button callback fired")
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._on_button("print"), self._loop
            )

    # -- state-aware action router ---------------------------------------

    async def _on_button(self, button: str) -> None:
        """Route a physical button press.

        Green (capture) = SELECT / CONFIRM
        Red (print) = CYCLE / NEXT

        On choose/template/effect screens, buttons send WebSocket
        events that the frontend handles for cycling and selecting.
        """
        state = self._sm.state
        print(f"[GPIO] Button '{button}' pressed in state {state}")

        if state == BoothState.IDLE:
            # Either button wakes up
            await self._sm.trigger("start")

        elif state == BoothState.CHOOSE:
            # Red = cycle, Green = select — handled by frontend
            await self._broadcast({
                "type": "button",
                "action": "select" if button == "capture" else "cycle",
            })

        elif state == BoothState.PREVIEW:
            # Either button cancels during countdown
            await self._sm.trigger("cancel")

        elif state in (BoothState.CAPTURE, BoothState.PROCESSING):
            pass

        elif state == BoothState.REVIEW:
            if button == "capture":
                # Green = done
                await self._sm.trigger("done")
            else:
                # Red = retake
                await self._sm.trigger("retake")

        elif state == BoothState.PRINT:
            await self._sm.trigger("done")

        elif state == BoothState.THANKYOU:
            await self._sm.trigger("start")

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def set_state_leds(self, state: BoothState):
        if not self._capture_led:
            return
        # Turn all off first
        self._capture_led.off()
        self._print_led.off()

        if state == BoothState.IDLE:
            self._capture_led.blink(on_time=1, off_time=1)
        elif state == BoothState.CHOOSE:
            self._capture_led.blink(on_time=0.5, off_time=0.5)
            self._print_led.blink(on_time=0.5, off_time=0.5)
        elif state == BoothState.PREVIEW:
            self._capture_led.on()
        elif state == BoothState.CAPTURE:
            self._capture_led.blink(on_time=0.1, off_time=0.1)
        elif state == BoothState.PROCESSING:
            self._capture_led.blink(on_time=0.3, off_time=0.3)
            self._print_led.blink(on_time=0.3, off_time=0.3)
        elif state == BoothState.REVIEW:
            self._capture_led.on()
            self._print_led.on()
        elif state == BoothState.PRINT:
            self._print_led.on()

    def close(self):
        for device in [
            self._capture_btn,
            self._print_btn,
            self._capture_led,
            self._print_led,
        ]:
            if device:
                try:
                    device.close()
                except Exception:
                    pass
        logger.info("GPIO closed")
