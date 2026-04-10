"""Built-in picture plugin -- handles image processing and composition."""

import asyncio
import logging

from app.models.state import BoothState
from app.plugins.hookspec import hookimpl

logger = logging.getLogger(__name__)


class PicturePlugin:
    def __init__(self, config, broadcast, share_service=None, counter_service=None):
        self._config = config
        self._broadcast = broadcast
        self._share_service = share_service
        self._counter_service = counter_service
        self._pipeline = None

    @hookimpl
    def booth_startup(self, app):
        from app.processing.pipeline import ProcessingPipeline

        self._pipeline = ProcessingPipeline()
        sm = app.state.state_machine
        sm.register_hook("state_processing_enter", self._on_processing_enter)
        sm.register_hook("state_processing_do", self._on_processing_do)

    async def _on_processing_enter(self, session, **kwargs):
        """Start processing the captures."""
        if not session:
            return

        await self._broadcast({
            "type": "processing_progress",
            "step": "compositing",
            "percent": 10,
        })

        try:
            footer_vars = {
                "event_name": self._config.sharing.event_name,
            }

            await self._broadcast({
                "type": "processing_progress",
                "step": "compositing",
                "percent": 30,
            })

            if session.mode in ("gif", "boomerang"):
                from datetime import datetime as dt
                from pathlib import Path

                from app.processing.gif import (
                    create_templated_boomerang,
                    create_templated_gif,
                )

                # Apply effect per-frame during template compositing
                effect = session.selected_effect

                date_str = dt.now().strftime("%Y-%m-%d")
                output_dir = (
                    Path(self._config.general.save_dir) / "photos" / date_str
                )
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / f"{session.id}.gif"

                footer_vars = {
                    "event_name": self._config.sharing.event_name,
                }

                # Build chromakey kwargs for GIF/boomerang
                ck_kwargs = {}
                if (
                    self._config.chromakey.enabled
                    and session.selected_background
                ):
                    ck_kwargs = {
                        "chromakey_background": session.selected_background,
                        "chromakey_hue_center": self._config.chromakey.hue_center,
                        "chromakey_hue_range": self._config.chromakey.hue_range,
                    }

                total_frames = len(session.captures)
                for i in range(total_frames):
                    pct = 20 + int(60 * (i / total_frames))
                    await self._broadcast({
                        "type": "processing_progress",
                        "step": "applying_effect",
                        "percent": pct,
                        "frame": i + 1,
                        "total_frames": total_frames,
                    })
                    await asyncio.sleep(0)  # Yield for WebSocket

                if session.mode == "boomerang":
                    await asyncio.to_thread(
                        create_templated_boomerang,
                        session.captures,
                        output_path,
                        template_name=session.layout_template,
                        footer_vars=footer_vars,
                        effect=effect,
                        **ck_kwargs,
                    )
                else:
                    await asyncio.to_thread(
                        create_templated_gif,
                        session.captures,
                        output_path,
                        template_name=session.layout_template,
                        footer_vars=footer_vars,
                        effect=effect,
                        **ck_kwargs,
                    )
                session.composite_path = output_path
            else:
                await self._pipeline.process(
                    session, self._config.picture, footer_vars,
                    branding=self._config.branding,
                    chromakey_config=(
                        self._config.chromakey
                        if self._config.chromakey.enabled
                        else None
                    ),
                )

            await self._broadcast({
                "type": "processing_progress",
                "step": "done",
                "percent": 100,
            })

            # Create share token and QR URL
            result_msg = {
                "type": "result_ready",
                "photo_id": session.id,
                "url": f"/api/gallery/{session.id}",
            }
            if self._share_service:
                try:
                    self._share_service.create_share(session)
                    result_msg["qr_url"] = f"/api/share/{session.share_token}/qr"
                except Exception as e:
                    logger.warning(f"Share token creation failed: {e}")

            await self._broadcast(result_msg)

            # Increment photo counter
            if self._counter_service:
                self._counter_service.increment_taken()
                await self._broadcast({
                    "type": "counter_update",
                    "counters": self._counter_service.counters,
                })

        except Exception as e:
            logger.error(f"Processing failed: {e}")
            await self._broadcast({
                "type": "error",
                "message": f"Processing failed: {e}",
            })
            # Mark session so _on_processing_do returns IDLE instead of stuck
            if session:
                session._processing_failed = True

    async def _on_processing_do(self, session, event=None, **kwargs):
        """Transition to review when processing is done, or idle on failure."""
        if session and getattr(session, "_processing_failed", False):
            return BoothState.IDLE
        if (event in ("enter_complete", "result_ready")
                and session and session.composite_path):
            return BoothState.REVIEW
        if session and session.composite_path:
            return BoothState.REVIEW
        return None
