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
        self, resolution: tuple[int, int] = (640, 480)
    ) -> None:
        from picamera2 import Picamera2

        self._preview_resolution = resolution
        self._picam2 = await asyncio.to_thread(
            Picamera2, self._camera_index
        )
        # Force RGB888 so capture_array returns clean 3-channel RGB
        # Use full sensor output to match capture FOV (otherwise preview crops)
        # Use 320x240 for fastest possible streaming
        stream_res = (320, 240)
        sensor_res = self._picam2.camera_properties.get(
            "PixelArraySize", (3280, 2464)
        )
        config = self._picam2.create_preview_configuration(
            main={"size": stream_res, "format": "RGB888"},
            raw={"size": sensor_res},
        )
        await asyncio.to_thread(self._picam2.configure, config)
        await asyncio.to_thread(self._picam2.start)
        await asyncio.sleep(2)
        self._running = True
        logger.info("PiCamera2 preview started at %s (RGB888)", resolution)

    async def stop_preview(self) -> None:
        self._running = False
        if self._picam2:
            try:
                await asyncio.to_thread(self._picam2.stop)
            except Exception:
                pass

    async def stream_mjpeg(self) -> AsyncIterator[bytes]:
        """Fast MJPEG: single thread call for capture + encode."""
        try:
            import cv2
            use_cv2 = True
        except ImportError:
            use_cv2 = False

        def _grab_frame_cv2(picam2):
            arr = picam2.capture_array("main")
            _, jpeg = cv2.imencode(".jpg", arr, [cv2.IMWRITE_JPEG_QUALITY, 30])
            return jpeg.tobytes()

        def _grab_frame_pil(picam2):
            buf = io.BytesIO()
            picam2.capture_file(buf, format="jpeg")
            return buf.getvalue()

        grab = _grab_frame_cv2 if use_cv2 else _grab_frame_pil

        while self._running and self._picam2:
            try:
                frame = await asyncio.to_thread(grab, self._picam2)
                yield frame
            except Exception as e:
                logger.debug("Frame capture error: %s", e)
                await asyncio.sleep(0.05)

    async def capture_still(self, path: Path) -> Path:
        if not self._picam2:
            raise RuntimeError("Camera not started")
        path.parent.mkdir(parents=True, exist_ok=True)

        sensor_res = self._picam2.camera_properties.get(
            "PixelArraySize", (3280, 2464)
        )
        still_config = self._picam2.create_still_configuration(
            main={"size": sensor_res}
        )
        # Stop preview, capture full-res still, restart preview
        self._running = False
        await asyncio.to_thread(self._picam2.stop)
        await asyncio.to_thread(self._picam2.configure, still_config)
        await asyncio.to_thread(self._picam2.start)
        # Re-apply crop/zoom for the capture
        if hasattr(self, '_crop') and self._crop:
            self._apply_hardware_crop(self._crop)
            await asyncio.sleep(0.2)  # Let crop take effect
        image = await asyncio.to_thread(
            self._picam2.capture_image, "main"
        )
        await asyncio.to_thread(image.save, str(path), quality=95)
        # Restart preview with same config as initial start
        await asyncio.to_thread(self._picam2.stop)
        sensor_full = self._picam2.camera_properties.get(
            "PixelArraySize", (3280, 2464)
        )
        preview_config = self._picam2.create_preview_configuration(
            main={"size": self._preview_resolution, "format": "RGB888"},
            raw={"size": sensor_full},
        )
        await asyncio.to_thread(self._picam2.configure, preview_config)
        await asyncio.to_thread(self._picam2.start)
        # Re-apply crop/zoom if set
        if hasattr(self, '_crop') and self._crop:
            self._apply_hardware_crop(self._crop)
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
            # Grab frame from the running preview
            frame = await asyncio.to_thread(
                self._picam2.capture_array, "main"
            )
            from PIL import Image as PILImage

            img = PILImage.fromarray(frame, "RGB")
            img.save(str(path), quality=90)
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
                await asyncio.to_thread(self._picam2.stop)
            except Exception:
                pass
            try:
                await asyncio.to_thread(self._picam2.close)
            except Exception:
                pass
            self._picam2 = None
            logger.info("PiCamera2 released")
