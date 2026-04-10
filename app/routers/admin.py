"""Admin API endpoints for configuration and system management."""

import json
import platform
import shutil
import socket
import tempfile
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse

from app.config import save_config
from app.models.config_schema import AppConfig
from app.services.admin_auth import (
    generate_token,
    hash_password,
    verify_password,
)

# In-memory token store (tokens reset on server restart)
_valid_tokens: set[str] = set()


def check_admin_auth(request: Request) -> bool:
    """Check if request is authenticated for admin."""
    config = request.app.state.config
    password_hash = config.admin.password_hash if hasattr(config, "admin") else ""

    if not password_hash:
        return True  # No password set

    token = request.cookies.get("admin_token")
    return token in _valid_tokens if token else False


async def require_admin(request: Request):
    """Dependency that enforces admin auth on all routes except login."""
    if request.url.path.endswith("/login"):
        return
    if not check_admin_auth(request):
        raise HTTPException(401, "Admin authentication required")


router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


@router.post("/login")
async def admin_login(request: Request, response: Response):
    """Authenticate with admin password."""
    data = await request.json()
    password = data.get("password", "")
    config = request.app.state.config
    password_hash = config.admin.password_hash if hasattr(config, "admin") else ""

    if not password_hash:
        return {"status": "ok", "message": "No password required"}

    if not verify_password(password, password_hash):
        raise HTTPException(401, "Invalid password")

    token = generate_token()
    _valid_tokens.add(token)

    response.set_cookie(
        "admin_token",
        token,
        max_age=30 * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
    )
    return {"status": "ok"}


@router.post("/logout")
async def admin_logout(
    response: Response, admin_token: str = Cookie(None),
):
    """Clear admin session."""
    if admin_token:
        _valid_tokens.discard(admin_token)
    response.delete_cookie("admin_token")
    return {"status": "ok"}


@router.post("/set-password")
async def set_admin_password(request: Request):
    """Set or change admin password. Requires current auth if password already set."""
    data = await request.json()
    new_password = data.get("password", "")

    if not new_password or len(new_password) < 4:
        raise HTTPException(400, "Password must be at least 4 characters")

    config = request.app.state.config
    config.admin.password_hash = hash_password(new_password)
    save_config(config)

    return {"status": "ok", "message": "Password set"}


@router.post("/remove-password")
async def remove_admin_password(request: Request):
    """Remove admin password (disable auth)."""
    config = request.app.state.config
    config.admin.password_hash = ""
    save_config(config)

    return {"status": "ok", "message": "Password removed"}


@router.get("/auth-status")
async def auth_status(request: Request):
    """Check if admin auth is required and if current session is valid."""
    config = request.app.state.config
    password_hash = config.admin.password_hash if hasattr(config, "admin") else ""
    has_password = bool(password_hash)
    authenticated = check_admin_auth(request)
    return {"has_password": has_password, "authenticated": authenticated}


@router.get("/config")
async def get_config(request: Request):
    """Return full config as JSON."""
    config = request.app.state.config
    return config.model_dump()


@router.patch("/config")
async def update_config(request: Request):
    """Partial config update. Merges with existing config and saves to TOML."""
    updates = await request.json()
    config = request.app.state.config

    # Merge updates into current config
    current = config.model_dump()
    _deep_merge(current, updates)

    # Validate
    try:
        new_config = AppConfig(**current)
    except Exception as e:
        raise HTTPException(422, f"Invalid config: {e}")

    # Save
    save_config(new_config)
    request.app.state.config = new_config
    return {"status": "updated"}


@router.get("/system")
async def system_info(request: Request):
    """System information: disk, memory, camera, printer status."""
    info = {
        "platform": platform.machine(),
        "python": platform.python_version(),
        "hostname": platform.node(),
    }

    # Disk usage
    try:
        disk = shutil.disk_usage("/")
        info["disk"] = {
            "total_gb": round(disk.total / (1024**3), 1),
            "used_gb": round(disk.used / (1024**3), 1),
            "free_gb": round(disk.free / (1024**3), 1),
        }
    except Exception:
        info["disk"] = None

    # Memory
    try:
        import psutil

        mem = psutil.virtual_memory()
        info["memory"] = {
            "total_mb": round(mem.total / (1024**2)),
            "used_mb": round(mem.used / (1024**2)),
            "percent": mem.percent,
        }
    except Exception:
        info["memory"] = None

    # Camera
    camera = request.app.state.camera
    info["camera"] = {
        "available": camera is not None,
        "type": type(camera).__name__ if camera else None,
    }

    # Printer
    printer = getattr(request.app.state, "printer", None)
    info["printer"] = {
        "available": (
            printer is not None and printer.is_available if printer else False
        ),
        "name": (
            printer._printer_name
            if printer and hasattr(printer, "_printer_name")
            else None
        ),
    }

    # GPIO
    gpio = getattr(request.app.state, "gpio", None)
    info["gpio"] = {"available": gpio is not None}

    # Photo count
    share_service = getattr(request.app.state, "share_service", None)
    if share_service:
        info["photo_count"] = len(share_service.list_photos(limit=10000))
    else:
        info["photo_count"] = 0

    # Network IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        info["ip"] = s.getsockname()[0]
        s.close()
    except Exception:
        info["ip"] = "unknown"

    return info


@router.get("/templates")
async def list_templates():
    """List available photo layout templates."""
    from app.processing.templates import list_templates

    return {"templates": list_templates()}


@router.get("/templates/{name}")
async def get_template(name: str):
    """Get a template's JSON definition."""
    templates_dir = Path(__file__).parent.parent / "static" / "templates"
    path = templates_dir / f"{name}.json"
    if not path.exists():
        raise HTTPException(404, "Template not found")
    return json.loads(path.read_text())


@router.put("/templates/{name}")
async def save_template(name: str, request: Request):
    """Save/update a template definition."""
    data = await request.json()
    templates_dir = Path(__file__).parent.parent / "static" / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    path = templates_dir / f"{name}.json"
    path.write_text(json.dumps(data, indent=2))
    return {"status": "saved", "name": name}


@router.delete("/templates/{name}")
async def delete_template(name: str):
    """Delete a template."""
    templates_dir = Path(__file__).parent.parent / "static" / "templates"
    path = templates_dir / f"{name}.json"
    if not path.exists():
        raise HTTPException(404, "Template not found")
    remaining = list(templates_dir.glob("*.json"))
    if len(remaining) <= 1:
        raise HTTPException(400, "Cannot delete the last template")
    path.unlink()
    return {"status": "deleted"}


@router.get("/effects")
async def list_effects():
    """List available photo effects."""
    from app.processing.effects import list_effects

    return {"effects": list_effects()}


@router.get("/backgrounds")
async def list_backgrounds():
    """List available chromakey background images."""
    from app.processing.chromakey import list_backgrounds

    return {"backgrounds": list_backgrounds()}


@router.get("/sounds")
async def list_sounds(request: Request):
    """List available sound files and current sound configuration."""
    from pathlib import Path

    config = request.app.state.config
    sound_config = config.sound.model_dump()

    # Scan the sounds directory for available files
    sounds_dir = Path(__file__).parent.parent / "static" / "sounds"
    available_files = []
    if sounds_dir.is_dir():
        for f in sorted(sounds_dir.iterdir()):
            if f.suffix.lower() in (".mp3", ".wav", ".ogg", ".webm"):
                available_files.append(f.name)

    return {
        "config": sound_config,
        "available_files": available_files,
        "sounds_dir": str(sounds_dir),
    }


@router.post("/theme")
async def upload_theme(request: Request):
    """Update theme CSS variables from JSON."""
    from pathlib import Path

    data = await request.json()
    variables = data.get("variables", {})

    # Generate CSS
    css_lines = [":root {"]
    for key, value in variables.items():
        css_lines.append(f"    {key}: {value};")
    css_lines.append("}")

    theme_path = Path(__file__).parent.parent / "static" / "css" / "theme.css"
    theme_path.write_text("\n".join(css_lines) + "\n")

    return {"status": "theme updated"}


@router.get("/connection")
async def connection_info(request: Request):
    """Connection info for headless mode -- URL and QR code for tablet."""
    config = request.app.state.config
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "localhost"

    port = config.server.port
    booth_url = f"http://{ip}:{port}/booth"
    admin_url = f"http://{ip}:{port}/admin"

    result = {
        "booth_url": booth_url,
        "admin_url": admin_url,
        "ip": ip,
        "port": port,
    }

    return result


@router.get("/counters")
async def get_counters(request: Request):
    """Return current photo/print counters."""
    counters = getattr(request.app.state, "counters", None)
    if counters is None:
        return {
            "total_taken": 0, "total_printed": 0,
            "session_taken": 0, "session_printed": 0,
        }
    return counters.counters


@router.post("/counters/reset-session")
async def reset_session_counters(request: Request):
    """Reset session counters (preserves totals)."""
    counters = getattr(request.app.state, "counters", None)
    if counters:
        counters.reset_session()
    return {"status": "reset"}


@router.get("/analytics")
async def get_analytics(request: Request):
    """Event analytics: photos per hour, popular effects, etc."""
    share_service = request.app.state.share_service
    counters = getattr(request.app.state, "counters", None)

    photos = share_service.list_photos(limit=10000)

    # Photos per hour
    hours: Counter = Counter()
    for p in photos:
        created_at = p.get("created_at", "")
        if len(created_at) >= 13:
            hour = created_at[:13]  # "2026-04-09T14"
            hours[hour] += 1

    uptime = counters.uptime_seconds if counters else 0

    return {
        "counters": counters.counters if counters else {},
        "total_photos": len(photos),
        "photos_per_hour": dict(sorted(hours.items())),
        "recent_photos": photos[:10],
        "uptime_seconds": uptime,
    }


@router.get("/backup")
async def create_backup(request: Request):
    """Create a ZIP archive of all photos and gallery DB."""
    config = request.app.state.config
    data_dir = Path(config.general.save_dir)

    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add all photos
        photos_dir = data_dir / "photos"
        if photos_dir.exists():
            for photo in photos_dir.rglob("*"):
                if photo.is_file():
                    zf.write(photo, f"photos/{photo.relative_to(photos_dir)}")
        # Add raw photos too
        raw_dir = data_dir / "raw"
        if raw_dir.exists():
            for photo in raw_dir.rglob("*"):
                if photo.is_file():
                    zf.write(photo, f"raw/{photo.relative_to(raw_dir)}")
        # Add gallery DB
        db_path = data_dir / "gallery.db"
        if db_path.exists():
            zf.write(db_path, "gallery.db")
        # Add counters
        counters_path = data_dir / "counters.json"
        if counters_path.exists():
            zf.write(counters_path, "counters.json")

    return FileResponse(
        tmp.name,
        media_type="application/zip",
        filename=f"photobooth_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
    )


@router.get("/camera/framing")
async def get_camera_framing(request: Request):
    """Return current camera framing/zoom settings."""
    config = request.app.state.config
    return {
        "crop_x": config.camera.crop_x,
        "crop_y": config.camera.crop_y,
        "crop_width": config.camera.crop_width,
        "crop_height": config.camera.crop_height,
        "zoom": config.camera.zoom,
        "mirror_preview": config.camera.mirror_preview,
        "mirror_capture": config.camera.mirror_capture,
    }


@router.patch("/camera/framing")
async def update_camera_framing(request: Request):
    """Live-update camera framing. Changes apply immediately to the preview."""
    data = await request.json()
    config = request.app.state.config
    camera = request.app.state.camera

    # Update config
    framing_keys = [
        "crop_x", "crop_y", "crop_width", "crop_height",
        "zoom", "mirror_preview", "mirror_capture",
    ]
    for key in framing_keys:
        if key in data:
            setattr(config.camera, key, data[key])

    # Apply to camera immediately — always use the full config state
    if camera:
        from app.camera.base import CropRegion

        camera.set_crop(CropRegion(
            config.camera.crop_x,
            config.camera.crop_y,
            config.camera.crop_width,
            config.camera.crop_height,
        ))

        # Apply mirror settings
        if "mirror_preview" in data:
            camera._mirror_preview = data["mirror_preview"]
        if "mirror_capture" in data:
            camera._mirror_capture = data["mirror_capture"]

    # Save config
    save_config(config)
    request.app.state.config = config

    return {"status": "updated"}


@router.post("/branding/logo")
async def upload_logo(file: UploadFile = File(...)):
    """Upload a company/event logo."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "File must be an image")

    branding_dir = Path(__file__).parent.parent / "static" / "branding"
    branding_dir.mkdir(parents=True, exist_ok=True)

    # Determine extension from content type
    ext = file.content_type.split("/")[-1]
    if ext == "svg+xml":
        ext = "svg"
    logo_path = branding_dir / f"logo.{ext}"

    # Remove any existing logo files
    for existing in branding_dir.glob("logo.*"):
        existing.unlink()

    content = await file.read()
    logo_path.write_bytes(content)

    return {"status": "uploaded", "url": f"/static/branding/logo.{ext}"}


@router.delete("/branding/logo")
async def delete_logo():
    """Remove the uploaded logo."""
    branding_dir = Path(__file__).parent.parent / "static" / "branding"
    for existing in branding_dir.glob("logo.*"):
        existing.unlink()
    return {"status": "deleted"}


@router.get("/branding")
async def get_branding():
    """Get current branding info (logo URL, etc.)."""
    branding_dir = Path(__file__).parent.parent / "static" / "branding"
    logo_url = None
    if branding_dir.exists():
        for f in branding_dir.glob("logo.*"):
            logo_url = f"/static/branding/{f.name}"
            break
    return {"logo_url": logo_url}


@router.get("/cloud-gallery/test")
async def test_cloud_gallery(request: Request):
    """Test cloud gallery connection by fetching gallery info."""
    config = request.app.state.config
    if not config.cloud_gallery.enabled:
        return {"connected": False, "error": "Cloud gallery not enabled"}

    if not (
        config.cloud_gallery.api_url
        and config.cloud_gallery.api_key
        and config.cloud_gallery.gallery_id
    ):
        return {"connected": False, "error": "Missing API URL, key, or gallery ID"}

    cloud_svc = getattr(request.app.state, "cloud_gallery", None)
    if not cloud_svc:
        # Create a temporary service for testing
        from app.services.cloud_gallery import CloudGalleryService

        cloud_svc = CloudGalleryService(
            api_url=config.cloud_gallery.api_url,
            api_key=config.cloud_gallery.api_key,
            gallery_id=config.cloud_gallery.gallery_id,
        )

    try:
        info = await cloud_svc.get_gallery_info()
        if info:
            return {
                "connected": True,
                "gallery_name": info.get("name", ""),
                "slug": info.get("slug", ""),
            }
        return {"connected": False, "error": "Failed to fetch gallery info"}
    except Exception as e:
        return {"connected": False, "error": str(e)}


@router.get("/events")
async def list_events(request: Request):
    """List all events/albums (local DB is source of truth)."""
    share_service = request.app.state.share_service
    albums = share_service.list_albums()

    # Include cloud connectivity status so the UI knows what's available
    cloud = getattr(request.app.state, "cloud_gallery", None)
    cloud_configured = bool(cloud and cloud.is_configured)

    return {"events": albums, "cloud_configured": cloud_configured}


@router.post("/events")
async def create_event(request: Request):
    """Create a new event. Local album always; cloud gallery if configured."""
    data = await request.json()
    name = data.get("name", "")
    if not name:
        raise HTTPException(400, "Event name required")

    share_service = request.app.state.share_service
    cloud = getattr(request.app.state, "cloud_gallery", None)

    cloud_gallery_id = ""
    slug = data.get("slug", "")

    # If cloud gallery is configured, also create there
    if cloud and cloud.is_configured:
        try:
            result = await cloud.create_gallery(name, slug)
            if result:
                cloud_gallery_id = result["id"]
                slug = result.get("slug", slug)
                await cloud.publish_gallery(cloud_gallery_id)
        except Exception:
            pass  # Cloud failure shouldn't block local album creation

    album = share_service.create_album(name, slug, cloud_gallery_id)

    # Auto-activate the new album
    share_service.activate_album(album["id"])

    # Update event name in config
    config = request.app.state.config
    config.sharing.event_name = name

    # Update cloud gallery_id if applicable
    if cloud_gallery_id:
        config.cloud_gallery.gallery_id = cloud_gallery_id
        if cloud:
            cloud._gallery_id = cloud_gallery_id

    save_config(config)

    return {"event": album}


@router.post("/events/{event_id}/activate")
async def activate_event(event_id: str, request: Request):
    """Set an album as active -- new photos go to this album."""
    share_service = request.app.state.share_service
    share_service.activate_album(event_id)

    # Get album info for config updates
    albums = share_service.list_albums()
    album = next((a for a in albums if a["id"] == event_id), None)

    if album:
        config = request.app.state.config
        config.sharing.event_name = album["name"]

        # Update cloud gallery if synced
        cloud = getattr(request.app.state, "cloud_gallery", None)
        if album.get("cloud_gallery_id") and cloud:
            config.cloud_gallery.gallery_id = album["cloud_gallery_id"]
            cloud._gallery_id = album["cloud_gallery_id"]

        save_config(config)

    return {"status": "activated"}


@router.delete("/events/{event_id}")
async def delete_event(event_id: str, request: Request):
    """Delete an album. Also removes cloud gallery if synced."""
    share_service = request.app.state.share_service

    # Get album to check for cloud gallery
    albums = share_service.list_albums()
    album = next((a for a in albums if a["id"] == event_id), None)

    # Delete from cloud if synced
    if album and album.get("cloud_gallery_id"):
        cloud = getattr(request.app.state, "cloud_gallery", None)
        if cloud and cloud.is_configured:
            try:
                await cloud.delete_gallery(album["cloud_gallery_id"])
            except Exception:
                pass  # Cloud failure shouldn't block local deletion

    share_service.delete_album(event_id)
    return {"status": "deleted"}


def _deep_merge(base: dict, updates: dict) -> dict:
    """Deep merge updates into base dict."""
    for key, value in updates.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base
