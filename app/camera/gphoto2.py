"""Stub for future gPhoto2 DSLR camera backend."""

from collections.abc import AsyncIterator
from pathlib import Path

from app.camera.base import CameraBase


class GPhoto2Backend(CameraBase):
    """DSLR camera backend via gPhoto2. Not yet implemented."""

    @classmethod
    def detect(cls) -> bool:
        """Always False until gPhoto2 support is implemented."""
        return False

    async def start_preview(
        self, resolution: tuple[int, int] = (1920, 1080)
    ) -> None:
        raise NotImplementedError("gPhoto2 backend not yet implemented")

    async def stop_preview(self) -> None:
        raise NotImplementedError("gPhoto2 backend not yet implemented")

    async def stream_mjpeg(self) -> AsyncIterator[bytes]:
        raise NotImplementedError("gPhoto2 backend not yet implemented")
        yield  # pragma: no cover  # noqa: E501

    async def capture_still(self, path: Path) -> Path:
        raise NotImplementedError("gPhoto2 backend not yet implemented")

    async def capture_sequence(
        self, count: int, interval_ms: int, output_dir: Path
    ) -> list[Path]:
        raise NotImplementedError("gPhoto2 backend not yet implemented")

    async def close(self) -> None:
        raise NotImplementedError("gPhoto2 backend not yet implemented")
