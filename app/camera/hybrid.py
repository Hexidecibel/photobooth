"""Hybrid camera combining separate preview and capture backends.

Useful for setups like Pi camera (fast preview) + DSLR (high-res capture).
"""

import logging
from collections.abc import AsyncIterator
from pathlib import Path

from app.camera.base import CameraBase

logger = logging.getLogger(__name__)


class HybridCamera(CameraBase):
    """Delegates preview to one backend and capture to another."""

    def __init__(self, preview: CameraBase, capture: CameraBase):
        self._preview = preview
        self._capture = capture

    @classmethod
    def detect(cls) -> bool:
        """Always False — detection happens at the factory level."""
        return False

    async def start_preview(
        self, resolution: tuple[int, int] = (1920, 1080)
    ) -> None:
        await self._preview.start_preview(resolution)

    async def stop_preview(self) -> None:
        await self._preview.stop_preview()

    async def stream_mjpeg(self) -> AsyncIterator[bytes]:
        async for frame in self._preview.stream_mjpeg():
            yield frame

    async def capture_still(self, path: Path) -> Path:
        await self._preview.stop_preview()
        try:
            result = await self._capture.capture_still(path)
        finally:
            await self._preview.start_preview()
        return result

    async def capture_sequence(
        self, count: int, interval_ms: int, output_dir: Path
    ) -> list[Path]:
        await self._preview.stop_preview()
        try:
            result = await self._capture.capture_sequence(
                count, interval_ms, output_dir
            )
        finally:
            await self._preview.start_preview()
        return result

    async def close(self) -> None:
        await self._preview.close()
        await self._capture.close()
