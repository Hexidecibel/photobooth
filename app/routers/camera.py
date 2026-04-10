"""Camera streaming endpoints."""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.camera.base import CameraBase
from app.dependencies import get_camera

router = APIRouter(prefix="/api/camera", tags=["camera"])


@router.get("/stream")
async def camera_stream(camera: CameraBase = Depends(get_camera)):
    """MJPEG streaming endpoint for live camera preview."""

    async def generate():
        async for frame in camera.stream_mjpeg():
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + frame
                + b"\r\n"
            )

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
