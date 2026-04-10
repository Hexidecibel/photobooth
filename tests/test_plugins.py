import tempfile
import textwrap
from pathlib import Path

from app.plugins.hookspec import PhotoboothHookSpec, hookimpl
from app.services.plugin_manager import PluginManager


class MockPlugin:
    @hookimpl
    def booth_configure(self, config):
        config["_test"] = True


class CameraPluginA:
    @hookimpl
    def setup_camera(self, config):
        return "camera_a"


class CameraPluginB:
    @hookimpl
    def setup_camera(self, config):
        return "camera_b"


class CameraPluginNone:
    @hookimpl
    def setup_camera(self, config):
        return None


def test_plugin_manager_creation():
    pm = PluginManager()
    assert pm is not None
    assert pm.hook is not None


def test_register_plugin():
    pm = PluginManager()
    plugin = MockPlugin()
    pm.register(plugin, name="mock")
    names = pm.list_plugins()
    assert any("mock" in n for n in names)


def test_hook_dispatch():
    pm = PluginManager()
    pm.register(MockPlugin(), name="mock")
    config = {}
    pm.hook.booth_configure(config=config)
    assert config["_test"] is True


def test_firstresult_hook():
    pm = PluginManager()
    # Register in order: None first, then A
    pm.register(CameraPluginNone(), name="cam_none")
    pm.register(CameraPluginA(), name="cam_a")
    pm.register(CameraPluginB(), name="cam_b")
    # firstresult returns the first non-None, which is the last registered
    # (pluggy calls in LIFO order by default)
    result = pm.hook.setup_camera(config={})
    assert result is not None
    assert result in ("camera_a", "camera_b")


def test_external_plugin_from_path():
    code = textwrap.dedent("""\
        import pluggy

        hookimpl = pluggy.HookimplMarker("photobooth")

        @hookimpl
        def booth_configure(config):
            config["_external"] = True
    """)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False
    ) as f:
        f.write(code)
        f.flush()
        tmp_path = f.name

    pm = PluginManager()
    pm.load_external(paths=[tmp_path])
    config = {}
    pm.hook.booth_configure(config=config)
    assert config["_external"] is True

    # Cleanup
    Path(tmp_path).unlink(missing_ok=True)


def test_hookspec_definitions_exist():
    expected_hooks = [
        "booth_configure",
        "booth_startup",
        "booth_cleanup",
        "state_enter",
        "state_do",
        "state_exit",
        "setup_camera",
        "pre_capture",
        "post_capture",
        "process_capture",
        "post_compose",
        "pre_print",
        "post_print",
        "on_share",
        "register_routes",
    ]
    for hook_name in expected_hooks:
        assert hasattr(PhotoboothHookSpec, hook_name), (
            f"Missing hookspec: {hook_name}"
        )
