from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response

router = APIRouter(prefix="/api/gallery", tags=["gallery"])


@router.get("/")
async def list_gallery(request: Request, limit: int = 50, offset: int = 0):
    share_service = request.app.state.share_service
    photos = share_service.list_photos(limit, offset)
    return {"photos": photos, "total": len(photos)}


@router.get("/{photo_id}")
async def get_photo(photo_id: str, request: Request):
    share_service = request.app.state.share_service
    photo = share_service.get_by_id(photo_id)
    if not photo:
        raise HTTPException(404, "Photo not found")

    photo_path = Path(photo["photo_path"])
    if not photo_path.exists():
        raise HTTPException(404, "Photo file not found")
    return FileResponse(str(photo_path), media_type="image/jpeg")


@router.get("/{photo_id}/thumbnail")
async def get_thumbnail(photo_id: str, request: Request, size: int = 400):
    """Serve a resized thumbnail for gallery grid."""
    share_service = request.app.state.share_service
    photo = share_service.get_by_id(photo_id)
    if not photo:
        raise HTTPException(404, "Photo not found")

    photo_path = Path(photo["photo_path"])
    if not photo_path.exists():
        raise HTTPException(404, "Photo file not found")

    try:
        from PIL import Image

        img = Image.open(photo_path)
        img.thumbnail((size, size), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return Response(content=buf.getvalue(), media_type="image/jpeg")
    except ImportError:
        # Pillow not installed, serve full image
        return FileResponse(str(photo_path), media_type="image/jpeg")


@router.post("/{photo_id}/share-token")
async def create_share_token(photo_id: str, request: Request):
    """Create a share token for a photo that doesn't have one."""
    share_service = request.app.state.share_service
    token = share_service.create_share_token(photo_id)
    if not token:
        raise HTTPException(404, "Photo not found")
    return {"share_token": token}


@router.delete("/{photo_id}")
async def delete_photo(photo_id: str, request: Request):
    share_service = request.app.state.share_service
    photo = share_service.get_by_id(photo_id)
    if not photo:
        raise HTTPException(404, "Photo not found")

    # Delete file
    photo_path = Path(photo["photo_path"])
    if photo_path.exists():
        photo_path.unlink()

    # Delete DB record
    share_service.delete_photo(photo_id)
    return {"status": "deleted"}
