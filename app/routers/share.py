from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response

router = APIRouter(tags=["share"])


@router.get("/api/share/{token}")
async def get_share_info(token: str, request: Request):
    share_service = request.app.state.share_service
    photo = share_service.get_by_token(token)
    if not photo:
        raise HTTPException(404, "Photo not found")
    email_service = getattr(request.app.state, "email_service", None)
    email_enabled = email_service is not None and email_service.is_available

    return {
        "id": photo["id"],
        "event_name": photo["event_name"],
        "created_at": photo["created_at"],
        "photo_url": f"/api/share/{token}/photo",
        "qr_url": f"/api/share/{token}/qr",
        "email_enabled": email_enabled,
    }


@router.get("/api/share/{token}/photo")
async def get_share_photo(token: str, request: Request):
    share_service = request.app.state.share_service
    photo = share_service.get_by_token(token)
    if not photo:
        raise HTTPException(404, "Photo not found")
    photo_path = Path(photo["photo_path"])
    if not photo_path.exists():
        raise HTTPException(404, "Photo file not found")
    return FileResponse(
        str(photo_path),
        media_type="image/jpeg",
        filename=f"photobooth_{photo['id']}.jpg",
    )


@router.get("/api/share/{token}/qr")
async def get_share_qr(token: str, request: Request):
    share_service = request.app.state.share_service
    config = request.app.state.config
    photo = share_service.get_by_token(token)
    if not photo:
        raise HTTPException(404, "Photo not found")

    url = share_service.get_share_url(token)
    qr_bytes = share_service.generate_qr_png(url, config.sharing.qr_size)
    if not qr_bytes:
        raise HTTPException(503, "QR generation not available")
    return Response(content=qr_bytes, media_type="image/png")


@router.get("/share/{token}")
async def share_page(token: str, request: Request):
    """Serve the guest-facing share page."""
    share_service = request.app.state.share_service
    photo = share_service.get_by_token(token)
    if not photo:
        raise HTTPException(404, "Photo not found")

    static_dir = Path(__file__).parent.parent / "static"
    share_html = static_dir / "share.html"
    if share_html.exists():
        return FileResponse(str(share_html))
    # Fallback inline HTML
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html><head><title>{photo['event_name']}</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>body{{margin:0;background:#111;color:#fff;font-family:system-ui;
    display:flex;flex-direction:column;align-items:center;padding:2rem}}
    img{{max-width:90vw;max-height:70vh;border-radius:12px;margin:1rem 0}}
    a{{display:inline-block;padding:1rem 2rem;background:#6c63ff;color:#fff;
    text-decoration:none;border-radius:8px;margin-top:1rem;font-size:1.1rem}}
    </style>
    </head><body>
    <h2>{photo['event_name']}</h2>
    <img src="/api/share/{token}/photo" alt="Your Photo">
    <a href="/api/share/{token}/photo" download="photobooth.jpg">
    Download Photo</a>
    </body></html>
    """)


@router.post("/api/share/{token}/email")
async def email_photo(token: str, request: Request):
    """Email a photo to the given address."""
    data = await request.json()
    email_addr = data.get("email")
    if not email_addr:
        raise HTTPException(400, "Email required")

    share_service = request.app.state.share_service
    email_service = getattr(request.app.state, "email_service", None)

    photo = share_service.get_by_token(token)
    if not photo:
        raise HTTPException(404, "Photo not found")

    if not email_service or not email_service.is_available:
        raise HTTPException(503, "Email not configured")

    success = await email_service.send_photo(
        email_addr,
        Path(photo["photo_path"]),
        photo.get("event_name", ""),
        share_service.get_share_url(token),
    )
    return {"status": "sent" if success else "failed"}
