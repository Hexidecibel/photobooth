"""PiCamera2 backend for Raspberry Pi cameras.

Imports picamera2 lazily so the module can be loaded on non-Pi systems.
Uses MJPEGEncoder for preview streaming and switch_mode_and_capture_image
for full-resolution stills.
"""

import asyncio
import io
import logging
import threading
from collections.abc import AsyncIterator
from pathlib import Path

from app.camera.base import CameraBase, CropRegion

logger = logging.getLogger(__name__)


class StreamingOutput(io.BufferedIOBase):
    """Thread-safe buffer for MJPEG frames from picamera2.

    Inherits from io.BufferedIOBase so picamera2's FileOutput accepts it.
    """

    def __init__(self) -> None:
        self.frame: bytes | None = None
        self.condition = threading.Condition()

    def write(self, buf: bytes) -> int:
        with self.condition:
            self.frame = buf
            self.condition.notify_all()
        return len(buf)

    def wait_for_frame(self, timeout: float = 1.0) -> bytes | None:
        with self.condition:
            self.condition.wait(timeout=timeout)
            return self.frame


class PiCamera2Backend(CameraBase):
    """Camera backend using the picamera2 library on Raspberry Pi."""

    def __init__(self, camera_index: int = 0):
        self._camera_index = camera_index
        self._picam2 = None
        self._output: StreamingOutput | None = None
        self._running = False
        self._preview_resolution: tuple[int, int] = (1920, 1080)

    @classmethod
    def detect(cls) -> bool:
        """Return True if a Pi camera is available via picamera2."""
        try:
            from picamera2 import Picamera2

            cameras = Picamera2.global_camera_info()
            return len(cameras) > 0
        except (ImportError, RuntimeError):
            return False

    async def start_preview(
        self, resolution: tuple[int, int] = (1920, 1080)
    ) -> None:
        from picamera2 import Picamera2
        from picamera2.encoders import MJPEGEncoder
        from picamera2.outputs import FileOutput

        self._preview_resolution = resolution
        self._picam2 = await asyncio.to_thread(
            Picamera2, self._camera_index
        )
        config = self._picam2.create_video_configuration(
            main={"size": resolution},
        )
        await asyncio.to_thread(self._picam2.configure, config)
        self._output = StreamingOutput()
        encoder = MJPEGEncoder(bitrate=8_000_000)
        await asyncio.to_thread(
            self._picam2.start_recording,
            encoder,
            FileOutput(self._output),
        )
        self._running = True
        logger.info("PiCamera2 preview started at %s", resolution)

    async def stop_preview(self) -> None:
        self._running = False
        if self._picam2:
            await asyncio.to_thread(self._picam2.stop_recording)

    async def stream_mjpeg(self) -> AsyncIterator[bytes]:
        while self._running and self._output:
            frame = await asyncio.to_thread(
                self._output.wait_for_frame, 1.0
            )
            if frame:
                yield frame

    async def capture_still(self, path: Path) -> Path:
        if not self._picam2:
            raise RuntimeError("Camera not started")
        path.parent.mkdir(parents=True, exist_ok=True)
        # Use the sensor's native resolution for best quality
        sensor_res = self._picam2.camera_properties.get(
            "PixelArraySize", (3280, 2464)
        )
        still_config = self._picam2.create_still_configuration(
            main={"size": sensor_res}
        )
        image = await asyncio.to_thread(
            self._picam2.switch_mode_and_capture_image,
            still_config,
            "main",
        )
        await asyncio.to_thread(image.save, str(path))
        # Switch back to preview mode
        preview_config = self._picam2.create_video_configuration(
            main={
                "size": self._preview_resolution,
                "format": "RGB888",
            }
        )
        await asyncio.to_thread(self._picam2.configure, preview_config)
        self._running = True
        logger.info("Still captured: %s", path)
        return path

    async def capture_sequence(
        self, count: int, interval_ms: int, output_dir: Path
    ) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        for i in range(count):
            path = output_dir / f"frame_{i:03d}.jpg"
            # For sequences, capture from the preview stream (lower res but fast)
            if self._output:
                frame = await asyncio.to_thread(
                    self._output.wait_for_frame, 1.0
                )
                if frame:
                    path.write_bytes(frame)
                    paths.append(path)
            if i < count - 1:
                await asyncio.sleep(interval_ms / 1000)
        return paths

    def set_crop(self, region: CropRegion) -> None:
        """Use picamera2 ScalerCrop for hardware-accelerated zoom."""
        self._crop = region
        self._apply_hardware_crop(region)

    def set_zoom(self, zoom: float) -> None:
        """Set digital zoom using hardware ScalerCrop on Pi."""
        if zoom <= 1.0:
            region = CropRegion()
        else:
            w = 1.0 / zoom
            h = 1.0 / zoom
            x = (1.0 - w) / 2
            y = (1.0 - h) / 2
            region = CropRegion(x, y, w, h)
        self._crop = region
        self._apply_hardware_crop(region)

    def _apply_hardware_crop(self, region: CropRegion) -> None:
        """Apply ScalerCrop control to the pi camera hardware."""
        if not self._picam2:
            return
        try:
            sensor_size = self._picam2.camera_properties["PixelArraySize"]
            sw, sh = sensor_size
            x = int(region.x * sw)
            y = int(region.y * sh)
            w = int(region.width * sw)
            h = int(region.height * sh)
            self._picam2.set_controls({"ScalerCrop": (x, y, w, h)})
            logger.info("Hardware ScalerCrop set: (%d, %d, %d, %d)", x, y, w, h)
        except Exception as e:
            logger.warning("Failed to set hardware ScalerCrop: %s", e)

    async def close(self) -> None:
        self._running = False
        if self._picam2:
            try:
                await asyncio.to_thread(self._picam2.stop_recording)
            except Exception:
                pass
            await asyncio.to_thread(self._picam2.close)
            self._picam2 = None
            logger.info("PiCamera2 released")
