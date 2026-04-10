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
            # Store effect for the upcoming capture
            if session:
                effect = kwargs.get("effect", "none")
                session.per_capture_effects.append(effect)
            return None
        return None

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
                frame_count = 8  # 8 frames for a good GIF
                paths = await self._camera.capture_sequence(
                    count=frame_count,
                    interval_ms=150,  # ~6.6fps burst
                    output_dir=raw_dir,
                )
                session.captures.extend(paths)
                await self._broadcast({
                    "type": "capture_complete",
                    "index": len(paths),
                    "total": len(paths),
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

        # Auto-advance after capture_enter completes
        if event in ("auto_advance", "capture_advance"):
            # GIF/boomerang captures all frames at once — go straight to processing
            if session.mode in ("gif", "boomerang"):
                return BoothState.PROCESSING
            if len(session.captures) < session.capture_count:
                return BoothState.PREVIEW
            return BoothState.PROCESSING

        # Fallback
        if session.mode in ("gif", "boomerang") or len(session.captures) >= session.capture_count:
            return BoothState.PROCESSING
        return BoothState.PREVIEW
