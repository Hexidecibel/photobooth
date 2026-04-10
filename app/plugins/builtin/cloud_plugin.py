"""Built-in cloud gallery plugin -- uploads photos to gallery.cush.rocks."""

import asyncio
import logging

from app.plugins.hookspec import hookimpl

logger = logging.getLogger(__name__)


class CloudPlugin:
    def __init__(self, config, cloud_service, broadcast):
        self._config = config
        self._cloud = cloud_service
        self._broadcast = broadcast
        self._gallery_slug = None

    @hookimpl
    def booth_startup(self, app):
        """Fetch gallery info on startup."""
        if self._cloud and self._cloud.is_configured:
            asyncio.create_task(self._fetch_gallery_slug())

    async def _fetch_gallery_slug(self):
        try:
            info = await self._cloud.get_gallery_info()
            if info:
                self._gallery_slug = info.get("slug", "")
                logger.info("Cloud gallery slug: %s", self._gallery_slug)
        except Exception as e:
            logger.warning("Failed to fetch gallery slug: %s", e)

    @hookimpl
    def on_share(self, session, share_url):
        """Upload photo to cloud gallery when a share is created."""
        if not self._cloud or not self._cloud.is_configured:
            return
        if not self._config.cloud_gallery.auto_upload:
            return
        if not session.composite_path:
            return

        # Upload in background (don't block the share flow)
        asyncio.create_task(self._upload_and_update(session))

    async def _upload_and_update(self, session):
        """Upload photo and broadcast cloud gallery URL."""
        try:
            result = await self._cloud.upload_photo(
                session.composite_path,
                title=self._config.sharing.event_name,
                description=f"Photo Booth \u2014 {session.mode}",
            )
            if result and self._gallery_slug:
                cloud_url = self._cloud.get_public_url(self._gallery_slug)
                logger.info("Photo uploaded to cloud: %s", cloud_url)
                await self._broadcast({
                    "type": "cloud_gallery_url",
                    "url": cloud_url,
                    "media_id": result.get("id", ""),
                })
        except Exception as e:
            logger.error("Cloud upload failed: %s", e)
