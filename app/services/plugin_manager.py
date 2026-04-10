import asyncio
import logging
from pathlib import Path

import pluggy

from app.plugins.hookspec import PhotoboothHookSpec

logger = logging.getLogger(__name__)


class PluginManager:
    def __init__(self):
        self._pm = pluggy.PluginManager("photobooth")
        self._pm.add_hookspecs(PhotoboothHookSpec)

    def load_builtins(self, app_state=None) -> None:
        """Load built-in plugins from app.plugins.builtin."""
        if app_state is None:
            return

        from app.plugins.builtin.camera_plugin import CameraPlugin
        from app.plugins.builtin.cloud_plugin import CloudPlugin
        from app.plugins.builtin.lights_plugin import LightsPlugin
        from app.plugins.builtin.picture_plugin import PicturePlugin
        from app.plugins.builtin.printer_plugin import PrinterPlugin
        from app.plugins.builtin.view_plugin import ViewPlugin
        from app.routers.booth import broadcast

        config = app_state.config
        camera = getattr(app_state, "camera", None)
        printer = getattr(app_state, "printer", None)
        share_service = getattr(app_state, "share_service", None)
        cloud_gallery = getattr(app_state, "cloud_gallery", None)

        self._pm.register(
            CameraPlugin(camera, config, broadcast), name="camera"
        )
        counter_service = getattr(app_state, "counters", None)
        self._pm.register(
            PicturePlugin(
                config, broadcast,
                share_service=share_service,
                counter_service=counter_service,
                cloud_service=cloud_gallery,
            ),
            name="picture",
        )
        self._pm.register(
            ViewPlugin(config, broadcast), name="view"
        )
        self._pm.register(LightsPlugin(config), name="lights")
        self._pm.register(
            PrinterPlugin(
                config, printer, broadcast,
                counter_service=counter_service,
            ),
            name="printer",
        )
        if cloud_gallery and cloud_gallery.is_configured:
            self._pm.register(
                CloudPlugin(config, cloud_gallery, broadcast),
                name="cloud",
            )

    def load_external(
        self,
        plugin_names: list[str] | None = None,
        paths: list[str] | None = None,
    ) -> None:
        """Discover and load external plugins via setuptools entry points."""
        discovered = self._pm.load_setuptools_entrypoints("photobooth")
        logger.info(f"Discovered {discovered} external plugins")

        # Load from filesystem paths
        for path_str in paths or []:
            path = Path(path_str)
            if path.exists():
                import importlib.util

                spec = importlib.util.spec_from_file_location(path.stem, path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    self._pm.register(module, name=path.stem)
                    logger.info(f"Loaded plugin from {path}")

    def register(self, plugin, name: str | None = None) -> None:
        """Register a plugin object or module."""
        self._pm.register(plugin, name=name)

    def unregister(self, plugin=None, name: str | None = None) -> None:
        """Unregister a plugin by reference or name."""
        self._pm.unregister(plugin=plugin, name=name)

    def list_plugins(self) -> list[str]:
        """Return human-readable names of all registered plugins."""
        names = []
        for plugin in self._pm.get_plugins():
            canonical = self._pm.get_name(plugin)
            if canonical:
                names.append(canonical)
            else:
                names.append(type(plugin).__qualname__)
        return names

    @property
    def hook(self):
        """Direct access to pluggy hooks (synchronous)."""
        return self._pm.hook

    async def ahook_call(self, hook_name: str, **kwargs):
        """Async-safe hook call. Runs sync hook impls in executor."""
        hook = getattr(self._pm.hook, hook_name)
        return await asyncio.to_thread(hook, **kwargs)
