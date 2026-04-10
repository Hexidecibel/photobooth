"""Abstract base class defining the camera interface."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CropRegion:
    """Fractional crop region within the full sensor frame."""

    x: float = 0.0
    y: float = 0.0
    width: float = 1.0
    height: float = 1.0


class CameraBase(ABC):
    """Base class all camera backends must implement."""

    @abstractmethod
    async def start_preview(
        self, resolution: tuple[int, int] = (1920, 1080)
    ) -> None:
        """Start camera preview / streaming."""

    @abstractmethod
    async def stop_preview(self) -> None:
        """Stop camera preview."""

    @abstractmethod
    async def stream_mjpeg(self) -> AsyncIterator[bytes]:
        """Yield JPEG frames for MJPEG streaming."""

    @abstractmethod
    async def capture_still(self, path: Path) -> Path:
        """Capture a full-resolution still image. Returns saved path."""

    @abstractmethod
    async def capture_sequence(
        self, count: int, interval_ms: int, output_dir: Path
    ) -> list[Path]:
        """Capture rapid sequence for GIF/boomerang. Returns list of saved paths."""

    @abstractmethod
    async def close(self) -> None:
        """Release camera resources."""

    def set_crop(self, region: CropRegion) -> None:
        """Set the crop/zoom region. Subclasses can override for hardware crop."""
        self._crop = region

    def set_zoom(self, zoom: float) -> None:
        """Set digital zoom (1.0 = none, 2.0 = 2x center crop)."""
        if zoom <= 1.0:
            self._crop = CropRegion()
        else:
            w = 1.0 / zoom
            h = 1.0 / zoom
            x = (1.0 - w) / 2
            y = (1.0 - h) / 2
            self._crop = CropRegion(x, y, w, h)

    @property
    def crop(self) -> CropRegion:
        """Current crop region."""
        return getattr(self, "_crop", CropRegion())

    @classmethod
    @abstractmethod
    def detect(cls) -> bool:
        """Check if this camera backend is available on the system."""
