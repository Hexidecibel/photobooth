"""Built-in picture plugin -- handles image processing and composition."""

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

            await self._pipeline.process(
                session, self._config.picture, footer_vars,
                branding=self._config.branding,
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

    async def _on_processing_do(self, session, event=None, **kwargs):
        """Auto-transition to review when processing is done."""
        if session and session.composite_path:
            return BoothState.REVIEW
        return None
