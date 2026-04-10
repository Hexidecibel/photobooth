# Plugin Development Guide

photobooth uses [pluggy](https://pluggy.readthedocs.io/) -- the same plugin framework that powers pytest -- to make nearly every aspect of the booth extensible. Plugins can hook into the lifecycle, state machine, camera, image processing, printing, sharing, and even add custom API endpoints.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Hook Reference](#hook-reference)
  - [Lifecycle Hooks](#lifecycle-hooks)
  - [State Machine Hooks](#state-machine-hooks)
  - [Camera Hooks](#camera-hooks)
  - [Processing Hooks](#processing-hooks)
  - [Printing Hooks](#printing-hooks)
  - [Sharing Hooks](#sharing-hooks)
  - [UI Hooks](#ui-hooks)
- [Plugin Registration](#plugin-registration)
  - [Setuptools Entry Points](#setuptools-entry-points)
  - [Filesystem Paths](#filesystem-paths)
- [Configuration](#configuration)
- [Examples](#examples)
  - [Cloud Upload Plugin (S3)](#cloud-upload-plugin-s3)
  - [Slack Notification Plugin](#slack-notification-plugin)
  - [Custom Effect Plugin](#custom-effect-plugin)
  - [Custom Camera Backend](#custom-camera-backend)
- [Testing Plugins](#testing-plugins)
- [Publishing](#publishing)

---

## Overview

The plugin system is built around **hooks** -- named extension points that fire at specific moments during the booth's operation. Plugins implement hook functions using the `@hookimpl` decorator. When the booth reaches a hook point, it calls every registered implementation.

Key concepts:

- **Hooks** are defined in `app/plugins/hookspec.py` using `@hookspec`
- **Implementations** use `@hookimpl` from the same module
- **firstresult** hooks stop after the first non-None return (used for camera setup, effect processing)
- **Regular** hooks call all implementations (used for lifecycle, notifications)
- **5 built-in plugins** handle core functionality: Camera, Picture, Printer, View, Lights

---

## Quick Start

A minimal plugin in 5 lines:

```python
from app.plugins.hookspec import hookimpl

class MyPlugin:
    @hookimpl
    def post_capture(self, session, image_path):
        print(f"Photo saved to {image_path}")
```

To load it, add the file path to `config.toml`:

```toml
[plugin]
paths = ["/home/pi/my_plugin.py"]
```

Or register it via setuptools entry point (see [Plugin Registration](#plugin-registration)).

---

## Hook Reference

### Lifecycle Hooks

#### `booth_configure(config: dict) -> None`

Called during startup before any services are initialized. Use this to register default config values or validate configuration.

**When it fires:** Early in the lifespan, after config is loaded.

```python
@hookimpl
def booth_configure(self, config: dict):
    # Set defaults for your plugin's config section
    config.setdefault("my_plugin", {
        "api_key": "",
        "upload_enabled": True,
    })
```

#### `booth_startup(app) -> None`

Called after all plugins are loaded and all services are initialized, but before the server starts accepting requests. The `app` parameter is the FastAPI application instance -- you can access `app.state` for camera, printer, config, etc.

**When it fires:** End of the lifespan startup phase.

```python
@hookimpl
def booth_startup(self, app):
    self.camera = app.state.camera
    self.config = app.state.config
    print("My plugin is ready!")
```

#### `booth_cleanup() -> None`

Called on application shutdown. Use this to close connections, flush buffers, release resources.

**When it fires:** Beginning of the lifespan shutdown phase.

```python
@hookimpl
def booth_cleanup(self):
    self.connection.close()
```

---

### State Machine Hooks

The booth progresses through these states:

```
idle -> choose -> preview -> capture -> processing -> review -> print -> thankyou -> idle
```

#### `state_enter(state: str, session) -> None`

Called when entering a new state. The `session` parameter is a `CaptureSession` object (or `None` if no session is active, e.g., during `idle`).

**When it fires:** After the state transition is committed, before any `state_do` processing.

```python
@hookimpl
def state_enter(self, state: str, session):
    if state == "capture":
        # Turn on flash, play countdown sound, etc.
        self.flash.on()
    elif state == "idle":
        self.flash.off()
```

#### `state_do(state: str, event: str, session, **kwargs)` (firstresult)

Process an event within the current state. Return the next `BoothState` to trigger a transition, or `None` to stay in the current state. This is a **firstresult** hook -- the first non-None return wins.

**When it fires:** When `StateMachine.trigger()` is called (button press, touch event, timer).

**Parameters:**
- `state` -- current state name (e.g., `"idle"`, `"capture"`)
- `event` -- the event name (e.g., `"start"`, `"choose"`, `"capture"`, `"print"`, `"done"`)
- `session` -- current `CaptureSession` or `None`
- `**kwargs` -- additional event data (e.g., `mode="photo"`, `count=4`)

```python
from app.models.state import BoothState

@hookimpl
def state_do(self, state: str, event: str, session, **kwargs):
    if state == "idle" and event == "start":
        return BoothState.CHOOSE  # Transition to choose screen
    return None  # Let other plugins handle it
```

#### `state_exit(state: str, session) -> None`

Called when leaving a state, before entering the next one.

**When it fires:** During `StateMachine.transition()`, after the exit is committed.

```python
@hookimpl
def state_exit(self, state: str, session):
    if state == "capture":
        self.flash.off()
```

---

### Camera Hooks

#### `setup_camera(config: dict)` (firstresult)

Return a camera instance. The first non-None result is used. This lets plugins provide custom camera backends.

**When it fires:** During startup, if camera auto-detection is configured.

```python
@hookimpl
def setup_camera(self, config: dict):
    if config["camera"]["backend"] == "my_custom_camera":
        return MyCustomCamera()
    return None  # Let default detection handle it
```

#### `pre_capture(session) -> None`

Called just before each individual capture (not once per session -- once per photo in a multi-shot sequence).

**When it fires:** Inside the capture loop, before `camera.capture_still()`.

```python
@hookimpl
def pre_capture(self, session):
    # Flash on, play shutter sound, etc.
    self.gpio.flash_on()
```

#### `post_capture(session, image_path) -> None`

Called after each individual capture with the path to the saved image.

**When it fires:** Inside the capture loop, after `camera.capture_still()` returns.

```python
@hookimpl
def post_capture(self, session, image_path):
    print(f"Captured: {image_path}")
    # Could do: upload to cloud, apply watermark, etc.
```

---

### Processing Hooks

#### `process_capture(image, effect: str | None, session)` (firstresult)

Apply an effect or filter to a single captured image. Receives a PIL `Image` and should return a modified PIL `Image`. This is a **firstresult** hook.

**When it fires:** During the processing state, once per captured image.

```python
from PIL import Image

@hookimpl
def process_capture(self, image: Image.Image, effect: str | None, session):
    if effect == "my_custom_effect":
        return self._apply_my_effect(image)
    return None  # Let the built-in effect handler process it
```

#### `post_compose(image, session)` (firstresult)

Post-process the final composited image (after all captures are placed in the template). Receives and returns a PIL `Image`. This is a **firstresult** hook.

**When it fires:** After the picture plugin composes the final layout, before saving.

```python
@hookimpl
def post_compose(self, image: Image.Image, session):
    # Add watermark, overlay, QR code, etc.
    return self._add_watermark(image)
```

---

### Printing Hooks

#### `pre_print(session) -> None`

Called just before a print job is submitted.

**When it fires:** When the user triggers print (button or UI), before CUPS job submission.

```python
@hookimpl
def pre_print(self, session):
    # Log print event, check paper supply, etc.
    self.print_counter += 1
```

#### `post_print(session, success: bool) -> None`

Called after a print job completes (or fails).

**When it fires:** After the CUPS job finishes.

```python
@hookimpl
def post_print(self, session, success: bool):
    if not success:
        self.send_alert("Print failed!")
```

---

### Sharing Hooks

#### `on_share(session, share_url: str) -> None`

Called when a share link is generated for a photo. Use this for cloud uploads, social media posting, notifications, etc.

**When it fires:** After `ShareService.create_share()` generates a token and URL.

```python
@hookimpl
def on_share(self, session, share_url: str):
    # Upload to cloud, post to Slack, etc.
    self.upload_to_s3(session.composite_path, share_url)
```

---

### UI Hooks

#### `register_routes(router) -> None`

Add custom API endpoints to the FastAPI application. The `router` parameter is a FastAPI `APIRouter`.

**When it fires:** During plugin loading.

```python
from fastapi import APIRouter

@hookimpl
def register_routes(self, router: APIRouter):
    @router.get("/api/my-plugin/status")
    async def my_status():
        return {"status": "running", "uploads": self.upload_count}
```

---

## Plugin Registration

### Setuptools Entry Points

The recommended way to distribute plugins. In your plugin's `pyproject.toml`:

```toml
[project]
name = "photobooth-my-plugin"
version = "1.0.0"

[project.entry-points.photobooth]
my_plugin = "photobooth_my_plugin:MyPlugin"
```

The entry point group is `photobooth`. The key (e.g., `my_plugin`) is the plugin name. The value points to the plugin class or module.

Install the plugin with pip:

```bash
pip install photobooth-my-plugin
```

The plugin manager discovers it automatically via `load_setuptools_entrypoints("photobooth")`.

### Filesystem Paths

For development or one-off plugins, point directly to Python files in `config.toml`:

```toml
[plugin]
paths = [
    "/home/pi/my_plugins/cloud_upload.py",
    "/home/pi/my_plugins/slack_notify.py",
]
```

The plugin manager loads each file as a module and registers it. The file can contain either a module with hook functions or a class with hook methods.

**Module-style plugin:**

```python
# my_plugin.py
from app.plugins.hookspec import hookimpl

@hookimpl
def post_capture(session, image_path):
    print(f"Captured: {image_path}")
```

**Class-style plugin (registered by the module's top-level instance):**

```python
# my_plugin.py
from app.plugins.hookspec import hookimpl

class MyPlugin:
    @hookimpl
    def post_capture(self, session, image_path):
        print(f"Captured: {image_path}")

# The plugin manager registers the module, so use module-level functions
# or register the class instance separately
```

---

## Configuration

Plugins can register their own configuration by using the `booth_configure` hook:

```python
@hookimpl
def booth_configure(self, config: dict):
    config.setdefault("my_plugin", {
        "api_key": "",
        "bucket_name": "photobooth-uploads",
        "enabled": True,
    })
```

These values can then be set in `config.toml`:

```toml
[my_plugin]
api_key = "sk-..."
bucket_name = "my-event-photos"
enabled = true
```

Access your config at runtime via `app.state.config`:

```python
@hookimpl
def booth_startup(self, app):
    config = app.state.config
    # Access via model_dump() or attribute access depending on how it's stored
```

---

## Examples

### Cloud Upload Plugin (S3)

Upload every photo to Amazon S3 after sharing:

```python
"""photobooth-s3-upload: Upload photos to S3."""

import logging
from pathlib import Path

import boto3

from app.plugins.hookspec import hookimpl

logger = logging.getLogger(__name__)


class S3UploadPlugin:
    def __init__(self):
        self._client = None
        self._bucket = None

    @hookimpl
    def booth_configure(self, config: dict):
        config.setdefault("s3_upload", {
            "bucket": "photobooth-photos",
            "region": "us-east-1",
            "prefix": "event/",
        })

    @hookimpl
    def booth_startup(self, app):
        cfg = app.state.config.model_dump().get("s3_upload", {})
        self._bucket = cfg.get("bucket", "photobooth-photos")
        self._client = boto3.client("s3", region_name=cfg.get("region", "us-east-1"))
        logger.info(f"S3 upload ready: {self._bucket}")

    @hookimpl
    def on_share(self, session, share_url: str):
        if not self._client or not session.composite_path:
            return
        path = Path(session.composite_path)
        key = f"event/{session.id}/{path.name}"
        try:
            self._client.upload_file(str(path), self._bucket, key)
            logger.info(f"Uploaded to s3://{self._bucket}/{key}")
        except Exception as e:
            logger.error(f"S3 upload failed: {e}")

    @hookimpl
    def booth_cleanup(self):
        self._client = None
```

### Slack Notification Plugin

Post a message to Slack after each photo:

```python
"""photobooth-slack: Post photos to a Slack channel."""

import logging

import httpx

from app.plugins.hookspec import hookimpl

logger = logging.getLogger(__name__)


class SlackPlugin:
    def __init__(self):
        self._webhook_url = None

    @hookimpl
    def booth_configure(self, config: dict):
        config.setdefault("slack", {
            "webhook_url": "",
            "channel": "#photobooth",
        })

    @hookimpl
    def booth_startup(self, app):
        cfg = app.state.config.model_dump().get("slack", {})
        self._webhook_url = cfg.get("webhook_url", "")

    @hookimpl
    def on_share(self, session, share_url: str):
        if not self._webhook_url:
            return
        try:
            httpx.post(self._webhook_url, json={
                "text": f"New photo booth pic! {share_url}",
            })
        except Exception as e:
            logger.error(f"Slack notification failed: {e}")
```

### Custom Effect Plugin

Add a custom image effect:

```python
"""photobooth-duotone: Duotone effect plugin."""

from PIL import Image, ImageEnhance

from app.plugins.hookspec import hookimpl


class DuotonePlugin:
    @hookimpl
    def process_capture(self, image: Image.Image, effect: str | None, session):
        if effect != "duotone":
            return None  # Let other handlers process
        # Convert to grayscale, then apply two-color toning
        gray = image.convert("L")
        r = gray.point(lambda x: min(255, int(x * 0.9 + 30)))
        g = gray.point(lambda x: min(255, int(x * 0.5)))
        b = gray.point(lambda x: min(255, int(x * 1.2)))
        result = Image.merge("RGB", (r, g, b))
        enhancer = ImageEnhance.Contrast(result)
        return enhancer.enhance(1.3)
```

To make this effect available in the UI, add it to the config:

```toml
[picture]
available_effects = ["none", "bw", "sepia", "vintage", "duotone"]
```

### Custom Camera Backend

Implement a custom camera (e.g., for a specific industrial camera):

```python
"""photobooth-flir: FLIR thermal camera backend."""

from pathlib import Path
from collections.abc import AsyncIterator

from app.camera.base import CameraBase
from app.plugins.hookspec import hookimpl


class FlirCamera(CameraBase):
    async def start_preview(self, resolution=(640, 480)):
        # Initialize FLIR SDK
        pass

    async def stop_preview(self):
        pass

    async def stream_mjpeg(self) -> AsyncIterator[bytes]:
        # Yield thermal JPEG frames
        while True:
            frame = self._get_thermal_frame()
            yield frame

    async def capture_still(self, path: Path) -> Path:
        # Capture thermal image
        pass

    async def capture_sequence(self, count, interval_ms, output_dir):
        # Capture rapid sequence
        pass

    async def close(self):
        pass

    @classmethod
    def detect(cls) -> bool:
        # Check if FLIR hardware is available
        return False


class FlirPlugin:
    @hookimpl
    def setup_camera(self, config: dict):
        if config["camera"]["backend"] == "flir":
            return FlirCamera()
        return None
```

---

## Testing Plugins

Use pytest with the FastAPI test client to test your plugins:

```python
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_my_plugin_hook(client):
    # Trigger the booth flow and verify your plugin's behavior
    response = client.get("/health")
    assert response.status_code == 200


def test_plugin_standalone():
    """Test plugin logic without the full app."""
    from my_plugin import MyPlugin

    plugin = MyPlugin()
    # Call hook methods directly
    plugin.post_capture(session=mock_session, image_path="/tmp/test.jpg")
```

For async hooks, use `pytest-asyncio`:

```python
import pytest

@pytest.mark.asyncio
async def test_async_hook():
    from my_plugin import MyPlugin
    plugin = MyPlugin()
    await plugin.some_async_method()
```

---

## Publishing

To share your plugin with the community:

1. **Create a package** with `pyproject.toml`:

```toml
[project]
name = "photobooth-my-plugin"
version = "1.0.0"
description = "My awesome photobooth plugin"
requires-python = ">=3.11"
dependencies = ["photobooth"]

[project.entry-points.photobooth]
my_plugin = "photobooth_my_plugin:MyPlugin"
```

2. **Structure your package:**

```
photobooth-my-plugin/
  pyproject.toml
  photobooth_my_plugin/
    __init__.py      # exports MyPlugin
  tests/
    test_plugin.py
```

3. **Publish to PyPI:**

```bash
pip install build twine
python -m build
twine upload dist/*
```

4. **Users install with:**

```bash
pip install photobooth-my-plugin
```

The plugin is discovered automatically via the setuptools entry point. No config changes needed (unless the plugin has its own settings).
