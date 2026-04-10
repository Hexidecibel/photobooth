"""PrinterService -- wraps pycups for photo printing.

All blocking CUPS calls are dispatched via asyncio.to_thread.
"""

import asyncio
import logging
from pathlib import Path

from app.models.config_schema import PrinterConfig

logger = logging.getLogger(__name__)


class PrinterService:
    def __init__(self, config: PrinterConfig):
        self._config = config
        self._conn = None
        self._printer_name: str | None = None
        self._setup()

    def _setup(self):
        try:
            import cups

            self._conn = cups.Connection()
            if self._config.printer_name:
                self._printer_name = self._config.printer_name
            else:
                self._printer_name = self._conn.getDefault()
            if self._printer_name:
                logger.info(f"Printer initialized: {self._printer_name}")
            else:
                logger.warning("No default printer configured")
        except (ImportError, RuntimeError) as e:
            logger.warning(f"CUPS not available: {e}")

    @property
    def is_available(self) -> bool:
        if not self._conn or not self._printer_name:
            return False
        try:
            printers = self._conn.getPrinters()
            return self._printer_name in printers
        except Exception:
            return False

    async def print_photo(self, image_path: Path, copies: int = 1) -> int | None:
        if not self._conn or not self._printer_name:
            logger.error("Printer not available")
            return None

        options = {}
        if copies > 1:
            options["copies"] = str(copies)

        try:
            job_id = await asyncio.to_thread(
                self._conn.printFile,
                self._printer_name,
                str(image_path),
                "Photobooth",
                options,
            )
            logger.info(f"Print job submitted: {job_id}")
            return job_id
        except Exception as e:
            logger.error(f"Print failed: {e}")
            return None

    async def get_job_status(self, job_id: int) -> str:
        if not self._conn:
            return "unavailable"
        try:
            attrs = await asyncio.to_thread(
                self._conn.getJobAttributes,
                job_id,
            )
            state = attrs.get("job-state", 0)
            state_map = {
                3: "pending",
                4: "held",
                5: "processing",
                6: "stopped",
                7: "cancelled",
                8: "aborted",
                9: "completed",
            }
            return state_map.get(state, "unknown")
        except Exception:
            return "error"

    def list_printers(self) -> dict:
        if not self._conn:
            return {}
        try:
            return self._conn.getPrinters()
        except Exception:
            return {}
