"""Hardware auto-detection and setup helpers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.hardware.gpio import GPIOController
from app.hardware.printer import PrinterService
from app.models.config_schema import AppConfig

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from app.services.state_machine import StateMachine

logger = logging.getLogger(__name__)


def setup_gpio(
    config: AppConfig,
    state_machine: StateMachine,
    broadcast: Callable[..., Awaitable[None]],
) -> GPIOController | None:
    try:
        gpio = GPIOController(config.controls, state_machine, broadcast)
        return gpio
    except Exception as e:
        logger.warning(f"GPIO setup failed: {e}")
        return None


def setup_printer(config: AppConfig) -> PrinterService | None:
    if not config.printer.enabled:
        return None
    try:
        printer = PrinterService(config.printer)
        return printer if printer.is_available else None
    except Exception as e:
        logger.warning(f"Printer setup failed: {e}")
        return None
