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
        camera = getattr(self._app, "camera", None)
        if camera is None:
            # Try to detect and start camera
            try:
                from app.camera.factory import auto_detect_camera

                config = self._app.config
                camera = await auto_detect_camera(config.camera)
                await camera.start_preview(config.camera.preview_resolution)
                self._app.camera = camera
                logger.info("Camera recovered")
            except Exception:
                pass  # Still no camera, try again next cycle

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
