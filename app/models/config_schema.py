"""Pydantic models for photobooth configuration.

Every section has sensible defaults so the app works out of the box
with zero configuration.
"""

from pydantic import BaseModel


class GeneralConfig(BaseModel):
    """General application settings."""

    language: str = "en"
    save_dir: str = "data"
    debug: bool = False
    autostart_delay: int = 3


class CameraConfig(BaseModel):
    """Camera hardware and capture settings."""

    backend: str = "auto"
    preview_resolution: tuple[int, int] = (1920, 1080)
    still_resolution: tuple[int, int] = (4608, 2592)
    webcam_index: int = 0
    flip_horizontal: bool = False
    rotation: int = 0
    # Digital zoom / crop region (fractional 0.0-1.0)
    crop_x: float = 0.0
    crop_y: float = 0.0
    crop_width: float = 1.0
    crop_height: float = 1.0
    zoom: float = 1.0
    mirror_preview: bool = True
    mirror_capture: bool = False


class PictureConfig(BaseModel):
    """Picture layout, effects, and rendering settings."""

    orientation: str = "portrait"
    capture_count: int = 4
    default_effect: str = "none"
    available_effects: list[str] = [
        "none",
        "bw",
        "sepia",
        "vintage",
        "warm",
        "cool",
        "cartoon",
        "pencil_sketch",
        "watercolor",
        "pop_art",
        "oil_painting",
    ]
    pose_prompts: list[str] = [
        "Strike a pose!",
        "Silly face!",
        "Say cheese!",
        "One more!",
    ]
    layout_template: str = "classic-4x6"
    # When true, guests choose template on the choose screen
    guest_picks_template: bool = False
    overlay_path: str = ""
    background_color: str = "#ffffff"
    background_image: str = ""
    footer_text: str = "{event_name} - {date}"
    dpi: int = 600


class ChromakeyConfig(BaseModel):
    """Green-screen / chroma key settings."""

    enabled: bool = False
    hue_center: int = 120
    hue_range: int = 40
    backgrounds: list[str] = []


class PrinterConfig(BaseModel):
    """Printer hardware and print-job settings."""

    enabled: bool = True
    printer_name: str = ""
    auto_print: bool = False
    max_pages: int = 0
    copies: int = 1


class ControlsConfig(BaseModel):
    """GPIO pin assignments and hardware-button settings."""

    capture_button_pin: int = 11
    print_button_pin: int = 7
    capture_led_pin: int = 15
    print_led_pin: int = 13
    debounce_ms: int = 300


class DisplayConfig(BaseModel):
    """Screen / kiosk display settings."""

    fullscreen: bool = True
    width: int = 1024
    height: int = 600
    hide_cursor: bool = True
    idle_timeout: int = 60  # seconds of inactivity before returning to idle


class SharingConfig(BaseModel):
    """Photo-sharing and QR-code settings."""

    enabled: bool = True
    base_url: str = ""
    qr_size: int = 200
    event_name: str = "Photo Booth"


class ServerConfig(BaseModel):
    """Web server settings."""

    host: str = "0.0.0.0"
    port: int = 8000


class SoundConfig(BaseModel):
    """Sound effects settings."""

    enabled: bool = True
    countdown_beep: str = "sounds/beep.wav"
    shutter: str = "sounds/shutter.wav"
    applause: str = "sounds/applause.wav"
    click: str = "sounds/click.wav"
    error: str = "sounds/error.wav"
    volume: float = 0.8  # 0.0 to 1.0


class PluginConfig(BaseModel):
    """Plugin discovery and loading settings."""

    enabled: list[str] = []
    paths: list[str] = []



class CloudGalleryConfig(BaseModel):
    """Cloud gallery integration (gallery.cush.rocks)."""

    enabled: bool = False
    api_url: str = ""  # e.g. "https://gallery.cush.rocks/api/v1"
    api_key: str = ""  # X-API-Key header value
    gallery_id: str = ""  # Gallery to upload photos to
    auto_upload: bool = True  # Upload every photo automatically


class AdminConfig(BaseModel):
    """Admin panel authentication settings."""

    password_hash: str = ""  # SHA-256 + salt hash. Empty = no auth required


class BrandingConfig(BaseModel):
    """Company/event branding settings."""

    logo_position: str = "top"  # top, bottom, overlay
    logo_size: int = 120  # px height on booth screen
    show_on_idle: bool = True
    show_on_prints: bool = True  # Include logo in printed photos
    company_name: str = ""
    tagline: str = ""


class EmailConfig(BaseModel):
    """Email sharing settings."""

    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    from_address: str = ""
    from_name: str = "Photo Booth"
    subject: str = "Your Photo Booth Photo!"
    body_template: str = "Here's your photo from {event_name}! Download it below."


class AppConfig(BaseModel):
    """Top-level configuration containing all sections."""

    general: GeneralConfig = GeneralConfig()
    camera: CameraConfig = CameraConfig()
    picture: PictureConfig = PictureConfig()
    chromakey: ChromakeyConfig = ChromakeyConfig()
    printer: PrinterConfig = PrinterConfig()
    controls: ControlsConfig = ControlsConfig()
    display: DisplayConfig = DisplayConfig()
    sharing: SharingConfig = SharingConfig()
    server: ServerConfig = ServerConfig()
    sound: SoundConfig = SoundConfig()
    plugin: PluginConfig = PluginConfig()
    email: EmailConfig = EmailConfig()
    branding: BrandingConfig = BrandingConfig()
    cloud_gallery: CloudGalleryConfig = CloudGalleryConfig()
    admin: AdminConfig = AdminConfig()
