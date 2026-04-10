"""OpenCV-based webcam backend.

Dev-friendly backend that works with any USB webcam. Imports cv2
lazily so the module can be loaded even when opencv is not installed.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from pathlib import Path

from app.camera.base import CameraBase

logger = logging.getLogger(__name__)


class OpenCVBackend(CameraBase):
    """Camera backend using OpenCV VideoCapture."""

    def __init__(self, device_index: int = 0):
        self._device_index = device_index
        self._cap = None  # cv2.VideoCapture
        self._running = False

    @classmethod
    def detect(cls) -> bool:
        """Return True if an OpenCV-compatible camera is available."""
        try:
            import cv2

            cap = cv2.VideoCapture(0)
            available = cap.isOpened()
            cap.release()
            return available
        except ImportError:
            return False

    async def start_preview(
        self, resolution: tuple[int, int] = (1920, 1080)
    ) -> None:
        import cv2

        self._cap = await asyncio.to_thread(
            cv2.VideoCapture, self._device_index
        )
        await asyncio.to_thread(
            self._cap.set, cv2.CAP_PROP_FRAME_WIDTH, resolution[0]
        )
        await asyncio.to_thread(
            self._cap.set, cv2.CAP_PROP_FRAME_HEIGHT, resolution[1]
        )
        self._running = True
        logger.info(
            "OpenCV preview started on device %d at %s",
            self._device_index,
            resolution,
        )

    async def stop_preview(self) -> None:
        self._running = False

    def _apply_crop(self, frame):
        """Apply crop region to a numpy frame."""
        crop = self.crop
        if crop.width >= 1.0 and crop.height >= 1.0 and crop.x <= 0.0 and crop.y <= 0.0:
            return frame
        h, w = frame.shape[:2]
        x1 = int(crop.x * w)
        y1 = int(crop.y * h)
        x2 = int((crop.x + crop.width) * w)
        y2 = int((crop.y + crop.height) * h)
        # Clamp to frame bounds
        x1 = max(0, min(x1, w))
        y1 = max(0, min(y1, h))
        x2 = max(0, min(x2, w))
        y2 = max(0, min(y2, h))
        if x2 <= x1 or y2 <= y1:
            return frame
        return frame[y1:y2, x1:x2]

    def _apply_mirror(self, frame, is_preview=True):
        """Apply horizontal flip if mirroring is enabled."""
        import cv2

        if is_preview:
            mirror = getattr(self, "_mirror_preview", False)
        else:
            mirror = getattr(self, "_mirror_capture", False)
        if mirror:
            return cv2.flip(frame, 1)
        return frame

    async def stream_mjpeg(self) -> AsyncIterator[bytes]:
        import cv2

        while self._running and self._cap and self._cap.isOpened():
            ret, frame = await asyncio.to_thread(self._cap.read)
            if not ret:
                await asyncio.sleep(0.01)
                continue
            frame = self._apply_crop(frame)
            frame = self._apply_mirror(frame, is_preview=True)
            _, jpeg = await asyncio.to_thread(
                cv2.imencode,
                ".jpg",
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, 85],
            )
            yield jpeg.tobytes()
            await asyncio.sleep(1 / 30)  # ~30fps

    async def capture_still(self, path: Path) -> Path:
        import cv2

        if not self._cap or not self._cap.isOpened():
            raise RuntimeError("Camera not started")
        ret, frame = await asyncio.to_thread(self._cap.read)
        if not ret:
            raise RuntimeError("Failed to capture frame")
        frame = self._apply_crop(frame)
        frame = self._apply_mirror(frame, is_preview=False)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Convert BGR to RGB, save via PIL for quality control
        from PIL import Image

        rgb = await asyncio.to_thread(
            cv2.cvtColor, frame, cv2.COLOR_BGR2RGB
        )
        img = Image.fromarray(rgb)
        await asyncio.to_thread(img.save, str(path), quality=95)
        logger.info("Still captured: %s", path)
        return path

    async def capture_sequence(
        self, count: int, interval_ms: int, output_dir: Path
    ) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        for i in range(count):
            path = output_dir / f"frame_{i:03d}.jpg"
            await self.capture_still(path)
            paths.append(path)
            if i < count - 1:
                await asyncio.sleep(interval_ms / 1000)
        return paths

    async def close(self) -> None:
        self._running = False
        if self._cap:
            await asyncio.to_thread(self._cap.release)
            self._cap = None
            logger.info("OpenCV camera released")
