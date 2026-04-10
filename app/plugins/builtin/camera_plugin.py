"""Built-in camera plugin -- handles preview countdown and capture logic."""

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
        """Camera preview is already running from startup. Just notify frontend."""

        # Send pose prompt for multi-capture sessions
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
        """Handle countdown timer in preview state."""
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

    async def _record_burst(self, session):
        """Record GIF/boomerang frames during preview state."""
        import asyncio as _asyncio
        import io as _io

        date_str = datetime.now().strftime("%Y-%m-%d")
        raw_dir = Path(self._config.general.save_dir) / "raw" / date_str / session.id
        raw_dir.mkdir(parents=True, exist_ok=True)

        frame_count = 8
        for i in range(frame_count):
            await self._broadcast({
                "type": "capture_progress",
                "frame": i + 1,
                "total": frame_count,
            })
            path = raw_dir / f"frame_{i:03d}.jpg"
            buf = _io.BytesIO()
            await _asyncio.to_thread(
                self._camera._picam2.capture_file,
                buf, format="jpeg",
            )
            path.write_bytes(buf.getvalue())
            session.captures.append(path)
            await _asyncio.sleep(0.1)

    async def _on_capture_enter(self, session, **kwargs):
        """Trigger a capture and auto-advance to next state."""
        if not session or not self._camera:
            return

        # Broadcast flash effect
        await self._broadcast({"type": "flash"})

        date_str = datetime.now().strftime("%Y-%m-%d")
        raw_dir = Path(self._config.general.save_dir) / "raw" / date_str / session.id
        raw_dir.mkdir(parents=True, exist_ok=True)

        try:
            if session.mode in ("gif", "boomerang"):
                # Rapid burst capture for GIF/boomerang
                frame_count = 8
                import asyncio as _asyncio
                import io as _io

                for i in range(frame_count):
                    await self._broadcast({
                        "type": "capture_progress",
                        "frame": i + 1,
                        "total": frame_count,
                    })
                    path = raw_dir / f"frame_{i:03d}.jpg"
                    # Use capture_file for correct colors (same as preview stream)
                    buf = _io.BytesIO()
                    await _asyncio.to_thread(
                        self._camera._picam2.capture_file,
                        buf, format="jpeg",
                    )
                    path.write_bytes(buf.getvalue())
                    session.captures.append(path)
                    await _asyncio.sleep(0.1)

                # Go straight to processing — broadcast complete and advance
                await self._broadcast({
                    "type": "processing_progress",
                    "step": "compositing",
                    "percent": 10,
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
            logger.error(f"Capture failed: {e}")
            await self._broadcast(
                {"type": "error", "message": f"Capture failed: {e}"}
            )

        # Frontend will send 'capture_advance' after receiving capture_complete

    async def _on_capture_do(self, session, event=None, **kwargs):
        """After capture, go to next preview or processing."""
        if not session:
            return BoothState.IDLE

        if event in ("enter_complete", "capture_advance"):
            # GIF/boomerang: straight to processing
            if session.mode in ("gif", "boomerang"):
                return BoothState.PROCESSING
            # Multi-shot: more captures needed?
            if len(session.captures) < session.capture_count:
                return BoothState.PREVIEW
            return BoothState.PROCESSING

        return None
