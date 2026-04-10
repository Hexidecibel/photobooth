import pluggy

hookspec = pluggy.HookspecMarker("photobooth")
hookimpl = pluggy.HookimplMarker("photobooth")


class PhotoboothHookSpec:
    """All available plugin hooks."""

    # --- Lifecycle ---
    @hookspec
    def booth_configure(self, config: dict) -> None:
        """Called during startup. Plugins can register config options."""

    @hookspec
    def booth_startup(self, app) -> None:
        """Called after all plugins loaded, before serving requests."""

    @hookspec
    def booth_cleanup(self) -> None:
        """Called on shutdown."""

    # --- State Machine ---
    @hookspec
    def state_enter(self, state: str, session) -> None:
        """Called when entering a state."""

    @hookspec(firstresult=True)
    def state_do(self, state: str, event: str, session, **kwargs):
        """Process an event in the current state. Return next state name or None."""

    @hookspec
    def state_exit(self, state: str, session) -> None:
        """Called when leaving a state."""

    # --- Camera ---
    @hookspec(firstresult=True)
    def setup_camera(self, config: dict):
        """Return a camera instance. First non-None result wins."""

    @hookspec
    def pre_capture(self, session) -> None:
        """Before each capture (trigger flash, play sound, etc.)."""

    @hookspec
    def post_capture(self, session, image_path) -> None:
        """After each capture."""

    # --- Processing ---
    @hookspec(firstresult=True)
    def process_capture(self, image, effect: str | None, session):
        """Apply effect/filter to a single capture. Return processed PIL Image."""

    @hookspec(firstresult=True)
    def post_compose(self, image, session):
        """Post-process the final composite. Return modified PIL Image."""

    # --- Printing ---
    @hookspec
    def pre_print(self, session) -> None:
        """Before printing."""

    @hookspec
    def post_print(self, session, success: bool) -> None:
        """After printing."""

    # --- Sharing ---
    @hookspec
    def on_share(self, session, share_url: str) -> None:
        """When a share link is generated. Use for cloud upload, notifications, etc."""

    # --- UI ---
    @hookspec
    def register_routes(self, router) -> None:
        """Plugins can add their own API endpoints."""
