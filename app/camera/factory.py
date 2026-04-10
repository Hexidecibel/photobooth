"""Auto-detection factory that picks the best available camera backend."""

import logging

from app.camera.base import CameraBase
from app.models.config_schema import CameraConfig

logger = logging.getLogger(__name__)


async def auto_detect_camera(config: CameraConfig) -> CameraBase:
    """Detect and return the best available camera backend."""
    if config.backend != "auto":
        return _create_specific(config)

    from app.camera.picamera2 import PiCamera2Backend
    from app.camera.webcam import OpenCVBackend

    pi_available = PiCamera2Backend.detect()
    usb_available = OpenCVBackend.detect()

    # Both available: hybrid mode only if explicitly configured
    if config.backend == "hybrid" and pi_available and usb_available:
        from app.camera.hybrid import HybridCamera

        logger.info("Using Hybrid camera (USB webcam preview + Pi camera capture)")
        preview = OpenCVBackend(config.webcam_index)
        capture = PiCamera2Backend()
        return HybridCamera(preview=preview, capture=capture)

    # Pi camera first (preferred)
    if pi_available:
        logger.info("Using PiCamera2 backend")
        return PiCamera2Backend()

    # USB webcam only
    if usb_available:
        logger.info("Using OpenCV webcam backend")
        return OpenCVBackend(config.webcam_index)

    raise RuntimeError(
        "No camera detected. Install picamera2 (Pi) or opencv-python (webcam)."
    )


def _create_specific(config: CameraConfig) -> CameraBase:
    """Create a specific backend by name."""
    from app.camera.picamera2 import PiCamera2Backend
    from app.camera.webcam import OpenCVBackend

    backends: dict[str, callable] = {
        "picamera2": lambda: PiCamera2Backend(),
        "opencv": lambda: OpenCVBackend(config.webcam_index),
    }
    if config.backend not in backends:
        raise ValueError(f"Unknown camera backend: {config.backend}")
    return backends[config.backend]()
