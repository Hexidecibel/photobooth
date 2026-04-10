"""Hybrid camera: USB webcam for smooth preview, Pi camera for captures.

The webcam runs the live MJPEG stream at 30fps. The Pi camera only
wakes up for actual photo captures (full sensor resolution).
"""

import asyncio
import io
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
        """Start Pi camera, capture full-res still, stop Pi camera."""
        from picamera2 import Picamera2

        logger.info("Hybrid: capturing still with Pi camera")
        path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize Pi camera fresh for this capture
        picam2 = await asyncio.to_thread(Picamera2)
        sensor_res = picam2.camera_properties.get(
            "PixelArraySize", (3280, 2464)
        )
        still_config = picam2.create_still_configuration(
            main={"size": sensor_res}
        )
        await asyncio.to_thread(picam2.configure, still_config)
        await asyncio.to_thread(picam2.start)
        await asyncio.sleep(0.5)  # Let AE/AWB settle

        # Apply crop if set
        if hasattr(self, '_crop') and self._crop:
            try:
                sw, sh = sensor_res
                x = int(self._crop.x * sw)
                y = int(self._crop.y * sh)
                w = int(self._crop.width * sw)
                h = int(self._crop.height * sh)
                picam2.set_controls({"ScalerCrop": (x, y, w, h)})
                await asyncio.sleep(0.2)
            except Exception as e:
                logger.warning("Hybrid crop failed: %s", e)

        image = await asyncio.to_thread(picam2.capture_image, "main")
        await asyncio.to_thread(image.save, str(path), quality=95)
        await asyncio.to_thread(picam2.stop)
        await asyncio.to_thread(picam2.close)
        logger.info("Hybrid: still captured at %s", path)
        return path

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
