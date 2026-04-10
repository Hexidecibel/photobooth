import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import load_config
from app.hardware.factory import setup_gpio, setup_printer
from app.routers import admin, api, booth, camera, gallery, share
from app.routers import printer as printer_router
from app.routers.booth import broadcast
from app.services.counter_service import CounterService
from app.services.email_service import EmailService
from app.services.plugin_manager import PluginManager
from app.services.share_service import ShareService
from app.services.state_machine import StateMachine
from app.services.tunnel_service import TunnelService
from app.services.watchdog import WatchdogService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize and tear down shared resources."""
    # Startup
    config = load_config()
    app.state.config = config

    # Camera (catch errors gracefully - may not have camera on dev machine)
    try:
        from app.camera.factory import auto_detect_camera

        cam = await auto_detect_camera(config.camera)
        await cam.start_preview(config.camera.preview_resolution)
        # Apply configured crop/zoom/mirror
        if config.camera.zoom != 1.0:
            cam.set_zoom(config.camera.zoom)
        elif config.camera.crop_width < 1.0 or config.camera.crop_height < 1.0:
            from app.camera.base import CropRegion

            cam.set_crop(CropRegion(
                config.camera.crop_x,
                config.camera.crop_y,
                config.camera.crop_width,
                config.camera.crop_height,
            ))
        cam._mirror_preview = config.camera.mirror_preview
        cam._mirror_capture = config.camera.mirror_capture
        app.state.camera = cam
    except Exception as e:
        logger.warning(f"No camera available: {e}")
        app.state.camera = None

    # State machine
    sm = StateMachine(broadcast=broadcast)
    app.state.state_machine = sm

    # GPIO hardware (buttons + LEDs) -- state-aware button handling
    gpio = setup_gpio(config, sm, broadcast)
    app.state.gpio = gpio
    if gpio:
        gpio.set_event_loop(asyncio.get_running_loop())

    # Printer
    printer = setup_printer(config)
    app.state.printer = printer

    # Tunnel service
    tunnel = TunnelService(config.network, config.server.port)
    tunnel_url = await tunnel.start()
    if tunnel_url:
        config.sharing.base_url = tunnel_url
    app.state.tunnel = tunnel

    # Share service
    share_svc = ShareService(config.sharing, data_dir=config.general.save_dir)
    app.state.share_service = share_svc

    # Counter service
    counter_svc = CounterService(data_dir=config.general.save_dir)
    app.state.counters = counter_svc

    # Email service
    email_svc = EmailService(config.email)
    app.state.email_service = email_svc

    # Cloud gallery service
    cloud_svc = None
    if config.cloud_gallery.enabled:
        from app.services.cloud_gallery import CloudGalleryService

        cloud_svc = CloudGalleryService(
            api_url=config.cloud_gallery.api_url,
            api_key=config.cloud_gallery.api_key,
            gallery_id=config.cloud_gallery.gallery_id,
        )
    app.state.cloud_gallery = cloud_svc

    # Plugin manager
    pm = PluginManager()
    pm.load_builtins(app.state)
    app.state.plugin_manager = pm

    # Wire GPIO into lights plugin if both are available
    if gpio:
        for plugin in pm._pm.get_plugins():
            if hasattr(plugin, "set_gpio"):
                plugin.set_gpio(gpio)

    # Watchdog service (auto-recovery for hardware failures)
    watchdog = WatchdogService(app.state)
    await watchdog.start()
    app.state.watchdog = watchdog

    # Fire startup hooks
    pm.hook.booth_startup(app=app)

    yield

    # Shutdown
    await watchdog.stop()
    if app.state.tunnel:
        await app.state.tunnel.stop()
    if app.state.gpio:
        app.state.gpio.close()
    if app.state.camera:
        await app.state.camera.close()


app = FastAPI(
    title="photobooth",
    description="A modern photo booth for Raspberry Pi.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api.router, prefix="/api")
app.include_router(admin.router)
app.include_router(camera.router)
app.include_router(booth.router)
app.include_router(printer_router.router)
app.include_router(share.router)
app.include_router(gallery.router)

# Static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Welcome to photobooth"}


@app.get("/booth")
async def serve_booth():
    """Serve the booth UI."""
    return FileResponse(str(static_dir / "index.html"))


@app.get("/admin")
async def serve_admin():
    """Serve the admin panel."""
    return FileResponse(str(static_dir / "admin.html"))


@app.get("/gallery")
async def serve_gallery():
    """Serve the event gallery page."""
    return FileResponse(str(static_dir / "gallery.html"))
