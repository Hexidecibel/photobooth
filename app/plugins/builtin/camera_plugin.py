"""Built-in camera plugin -- handles preview countdown and capture logic."""

import asyncio
import io
import logging
from datetime import datetime
from pathlib import Path

from app.models.state import BoothState
from app.plugins.hookspec import hookimpl

logger = logging.getLogger(__name__)


class CameraPlugin:
    def __init__(self, camera, config, broadcast):
        self._camera = camera
        self._config = config
        self._broadcast = broadcast

    @hookimpl
    def booth_startup(self, app):
        """Register state hooks with the state machine."""
        sm = app.state.state_machine
        sm.register_hook("state_preview_enter", self._on_preview_enter)
        sm.register_hook("state_preview_do", self._on_preview_do)
        sm.register_hook("state_capture_enter", self._on_capture_enter)
        sm.register_hook("state_capture_do", self._on_capture_do)

    async def _on_preview_enter(self, session, **kwargs):
        """Camera preview is already running from startup."""
        if session and session.capture_count > 1:
            capture_index = len(session.captures)
            prompts = self._config.picture.pose_prompts
            if capture_index < len(prompts):
                await self._broadcast({
                    "type": "pose_prompt",
                    "text": prompts[capture_index],
                    "capture": capture_index + 1,
                    "total": session.capture_count,
                })

    async def _on_preview_do(self, session, event=None, **kwargs):
        """Handle events in preview state."""
        if event in ("countdown_complete", "capture"):
            return BoothState.CAPTURE
        if event == "cancel":
            return BoothState.IDLE
        if event == "select_per_shot_effect":
            if session:
                effect = kwargs.get("effect", "none")
                session.per_capture_effects.append(effect)
            return None
        return None

    async def _on_capture_enter(self, session, **kwargs):
        """Trigger capture and advance."""
        if not session or not self._camera:
            return

        await self._broadcast({"type": "flash"})

        date_str = datetime.now().strftime("%Y-%m-%d")
        raw_dir = Path(self._config.general.save_dir) / "raw" / date_str / session.id
        raw_dir.mkdir(parents=True, exist_ok=True)

        try:
            if session.mode in ("gif", "boomerang"):
                # Stop MJPEG stream
                self._camera._running = False
                await asyncio.sleep(0.2)

                frame_count = 8

                # Capture ALL frames in one blocking call
                # This frees the event loop completely during capture
                def _burst_capture(picam2, output_dir, count):
                    import time
                    paths = []
                    for i in range(count):
                        path = output_dir / f"frame_{i:03d}.jpg"
                        buf = io.BytesIO()
                        picam2.capture_file(buf, format="jpeg")
                        path.write_bytes(buf.getvalue())
                        paths.append(path)
                        time.sleep(0.1)
                    return paths

                # Send initial message before blocking
                await self._broadcast({
                    "type": "capture_progress",
                    "frame": 0,
                    "total": frame_count,
                })

                paths = await asyncio.to_thread(
                    _burst_capture,
                    self._camera._picam2,
                    raw_dir,
                    frame_count,
                )
                session.captures.extend(paths)

                # Re-enable stream
                self._camera._running = True

                await self._broadcast({
                    "type": "capture_complete",
                    "index": frame_count,
                    "total": frame_count,
                })
            else:
                # Single still capture
                capture_index = len(session.captures)
                path = raw_dir / f"capture_{capture_index:03d}.jpg"
                saved_path = await self._camera.capture_still(path)
                session.captures.append(saved_path)
                await self._broadcast({
                    "type": "capture_complete",
                    "index": len(session.captures),
                    "total": session.capture_count,
                })
        except Exception as e:
            logger.error("Capture failed: %s", e)
            await self._broadcast(
                {"type": "error", "message": f"Capture failed: {e}"}
            )

    async def _on_capture_do(self, session, event=None, **kwargs):
        """After capture, advance to next state."""
        if not session:
            return BoothState.IDLE

        if event == "enter_complete":
            # GIF: burst is done, go to processing
            if session.mode in ("gif", "boomerang") and len(session.captures) > 0:
                return BoothState.PROCESSING
            # Photo: auto-advance
            if len(session.captures) >= session.capture_count:
                return BoothState.PROCESSING
            return BoothState.PREVIEW

        if event == "capture_advance":
            if session.mode in ("gif", "boomerang"):
                return BoothState.PROCESSING
            if len(session.captures) < session.capture_count:
                return BoothState.PREVIEW
            return BoothState.PROCESSING

        return None
