"""Hybrid camera: USB webcam for smooth preview, Pi camera for captures.

The webcam runs the live MJPEG stream at 30fps. The Pi camera only
wakes up for actual photo captures (full sensor resolution).
"""

import logging
from collections.abc import AsyncIterator
from pathlib import Path

from app.camera.base import CameraBase

logger = logging.getLogger(__name__)


class HybridCamera(CameraBase):
    """USB webcam preview + Pi camera capture."""

    def __init__(self, preview: CameraBase, capture: CameraBase):
        self._preview = preview
        self._capture = capture  # PiCamera2Backend — not started until needed

    @classmethod
    def detect(cls) -> bool:
        return False

    async def start_preview(
        self, resolution: tuple[int, int] = (640, 480)
    ) -> None:
        # Only start the webcam for preview
        await self._preview.start_preview(resolution)
        logger.info("Hybrid: webcam preview started")

    async def stop_preview(self) -> None:
        await self._preview.stop_preview()

    async def stream_mjpeg(self) -> AsyncIterator[bytes]:
        async for frame in self._preview.stream_mjpeg():
            yield frame

    async def capture_still(self, path: Path) -> Path:
        """Pause preview, delegate capture to capture backend, resume."""
        logger.info("Hybrid: capturing still with capture backend")
        await self._preview.stop_preview()
        try:
            result = await self._capture.capture_still(path)
        finally:
            await self._preview.start_preview()
        logger.info("Hybrid: still captured at %s", result)
        return result

    async def capture_sequence(
        self, count: int, interval_ms: int, output_dir: Path
    ) -> list[Path]:
        """Use webcam for GIF burst (already running, fast)."""
        return await self._preview.capture_sequence(
            count, interval_ms, output_dir
        )

    async def close(self) -> None:
        await self._preview.close()
        # Pi camera isn't running, nothing to close
