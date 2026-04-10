"""Tests for the camera abstraction layer."""

from unittest.mock import AsyncMock, patch

import pytest

from app.camera.base import CameraBase
from app.camera.hybrid import HybridCamera
from app.camera.webcam import OpenCVBackend
from app.models.config_schema import CameraConfig


def test_camera_base_is_abstract():
    """CameraBase cannot be instantiated directly."""
    with pytest.raises(TypeError):
        CameraBase()


def test_opencv_detect_without_cv2():
    """OpenCVBackend.detect() returns False when cv2 is not importable."""
    with patch.dict("sys.modules", {"cv2": None}):
        assert OpenCVBackend.detect() is False


@pytest.fixture
def mock_preview():
    """Mock camera backend used as the preview source."""
    return AsyncMock(spec=CameraBase)


@pytest.fixture
def mock_capture():
    """Mock camera backend used as the capture source."""
    return AsyncMock(spec=CameraBase)


@pytest.mark.asyncio
async def test_hybrid_delegates_preview(mock_preview, mock_capture):
    """HybridCamera delegates preview calls to the preview backend."""
    hybrid = HybridCamera(preview=mock_preview, capture=mock_capture)

    await hybrid.start_preview((1280, 720))
    mock_preview.start_preview.assert_awaited_once_with((1280, 720))

    await hybrid.stop_preview()
    mock_preview.stop_preview.assert_awaited_once()


@pytest.mark.asyncio
async def test_hybrid_delegates_capture(mock_preview, mock_capture, tmp_path):
    """HybridCamera pauses preview, delegates to capture, then resumes."""
    hybrid = HybridCamera(preview=mock_preview, capture=mock_capture)
    out_path = tmp_path / "photo.jpg"
    mock_capture.capture_still.return_value = out_path

    result = await hybrid.capture_still(out_path)

    assert result == out_path
    mock_preview.stop_preview.assert_awaited_once()
    mock_capture.capture_still.assert_awaited_once_with(out_path)
    mock_preview.start_preview.assert_awaited_once()


@pytest.mark.asyncio
async def test_factory_falls_back_to_opencv():
    """Factory returns OpenCVBackend when PiCamera2 is unavailable."""
    from app.camera.factory import auto_detect_camera
    from app.camera.picamera2 import PiCamera2Backend

    with (
        patch.object(PiCamera2Backend, "detect", return_value=False),
        patch.object(OpenCVBackend, "detect", return_value=True),
    ):
        config = CameraConfig(webcam_index=2)
        cam = await auto_detect_camera(config)

        assert isinstance(cam, OpenCVBackend)
        assert cam._device_index == 2


@pytest.mark.asyncio
async def test_factory_raises_when_no_camera():
    """Factory raises RuntimeError when no camera backend is available."""
    from app.camera.factory import auto_detect_camera
    from app.camera.picamera2 import PiCamera2Backend

    with (
        patch.object(PiCamera2Backend, "detect", return_value=False),
        patch.object(OpenCVBackend, "detect", return_value=False),
    ):
        config = CameraConfig()
        with pytest.raises(RuntimeError, match="No camera detected"):
            await auto_detect_camera(config)
