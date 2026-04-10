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

    tunnel = getattr(request.app.state, "tunnel", None)
    if tunnel and tunnel.public_url:
        result["tunnel_url"] = tunnel.public_url
        result["tunnel_active"] = tunnel.is_running
        result["tunnel_provider"] = config.network.tunnel_provider

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


def _deep_merge(base: dict, updates: dict) -> dict:
    """Deep merge updates into base dict."""
    for key, value in updates.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base
