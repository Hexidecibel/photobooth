"""Watchdog service -- monitors hardware health and attempts auto-recovery."""

import asyncio
import logging

logger = logging.getLogger(__name__)


class WatchdogService:
    """Monitors hardware health and attempts recovery."""

    def __init__(self, app_state):
        self._app = app_state
        self._running = False
        self._task = None

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Watchdog started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self):
        while self._running:
            await asyncio.sleep(10)  # Check every 10 seconds
            await self._check_camera()
            await self._check_printer()

    async def _check_camera(self):
        # Camera recovery is disabled — picamera2 doesn't handle
        # re-acquisition well. Restart the service instead.
        pass

    async def _check_printer(self):
        printer = getattr(self._app, "printer", None)
        if printer and not printer.is_available:
            # Try to reconnect
            try:
                from app.hardware.printer import PrinterService

                new_printer = PrinterService(self._app.config.printer)
                if new_printer.is_available:
                    self._app.printer = new_printer
                    logger.info("Printer recovered")
            except Exception:
                pass
