"""Built-in printer plugin -- handles print state logic."""

import asyncio
import logging

from app.plugins.hookspec import hookimpl

logger = logging.getLogger(__name__)


class PrinterPlugin:
    def __init__(self, config, printer, broadcast, counter_service=None):
        self._config = config
        self._printer = printer
        self._broadcast = broadcast
        self._counter_service = counter_service

    @hookimpl
    def booth_startup(self, app):
        sm = app.state.state_machine
        sm.register_hook("state_print_enter", self._on_print_enter)

    async def _on_print_enter(self, session, **kwargs):
        """When entering print state, submit the print job."""
        if not session or not session.composite_path:
            await self._broadcast({"type": "print_status", "status": "error"})
            return

        # Check print limit
        if self._config.printer.max_pages > 0 and self._counter_service:
            if (
                self._counter_service.counters.get("total_printed", 0)
                >= self._config.printer.max_pages
            ):
                await self._broadcast(
                    {"type": "print_status", "status": "limit_reached"}
                )
                return

        if not self._printer or not self._printer.is_available:
            # No printer -- just show the QR code, skip printing
            await self._broadcast({"type": "print_status", "status": "no_printer"})
            # Auto-transition to thankyou after a delay
            await asyncio.sleep(5)
            await self._broadcast({"type": "auto_transition", "target": "thankyou"})
            return

        await self._broadcast({"type": "print_status", "status": "printing"})

        copies = self._config.printer.copies
        job_id = await self._printer.print_photo(session.composite_path, copies)

        if job_id:
            # Poll for completion (simple approach)
            for _ in range(30):  # 30 second timeout
                status = await self._printer.get_job_status(job_id)
                if status in ("completed", "cancelled", "aborted"):
                    break
                await asyncio.sleep(1)

            await self._broadcast({"type": "print_status", "status": "done"})
            # Increment print counter
            if self._counter_service:
                self._counter_service.increment_printed()
        else:
            await self._broadcast({"type": "print_status", "status": "error"})
