import asyncio
import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


class CloudGalleryService:
    def __init__(self, api_url: str, api_key: str, gallery_id: str):
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._gallery_id = gallery_id
        self._headers = {"X-API-Key": api_key}

    @property
    def is_configured(self) -> bool:
        return bool(self._api_url and self._api_key and self._gallery_id)

    async def upload_photo(
        self, photo_path: Path, title: str = "", description: str = ""
    ) -> dict | None:
        """Upload a photo to the cloud gallery.

        Returns media record or None on failure.
        """
        if not self.is_configured:
            return None

        try:
            file_size = photo_path.stat().st_size
            filename = photo_path.name
            content_type = (
                "image/gif" if filename.endswith(".gif") else "image/jpeg"
            )

            async with httpx.AsyncClient(timeout=60) as client:
                # Step 1: Get upload URL
                resp = await client.post(
                    f"{self._api_url}/galleries/{self._gallery_id}"
                    "/media/upload-url",
                    headers=self._headers,
                    json={
                        "filename": filename,
                        "contentType": content_type,
                        "fileSize": file_size,
                    },
                )
                if resp.status_code != 200:
                    logger.error(
                        "Upload URL failed: %s %s",
                        resp.status_code,
                        resp.text,
                    )
                    return None

                upload_data = resp.json()["data"]
                media_id = upload_data["mediaId"]
                upload_url = upload_data["uploadUrl"]

                # Step 2: Upload file
                file_bytes = await asyncio.to_thread(photo_path.read_bytes)
                base_url = self._api_url.rsplit("/api", 1)[0]
                upload_resp = await client.put(
                    f"{base_url}{upload_url}",
                    headers={
                        **self._headers,
                        "Content-Type": content_type,
                    },
                    content=file_bytes,
                )
                if upload_resp.status_code not in (200, 201):
                    logger.error(
                        "Upload failed: %s %s",
                        upload_resp.status_code,
                        upload_resp.text,
                    )
                    return None

                media_record = upload_resp.json().get("data", {})

                # Step 3: Confirm with metadata + dimensions
                confirm_data = {"mediaId": media_id}
                if title:
                    confirm_data["title"] = title
                if description:
                    confirm_data["description"] = description

                # Get image dimensions
                try:
                    from PIL import Image as PILImage
                    img = await asyncio.to_thread(PILImage.open, photo_path)
                    confirm_data["width"] = img.width
                    confirm_data["height"] = img.height
                except Exception:
                    pass

                await client.post(
                    f"{self._api_url}/galleries/{self._gallery_id}"
                    "/media/confirm",
                    headers=self._headers,
                    json=confirm_data,
                )

                logger.info(
                    "Uploaded to cloud gallery: %s (media_id: %s)",
                    filename,
                    media_id,
                )
                return media_record

        except Exception as e:
            logger.error("Cloud gallery upload failed: %s", e)
            return None

    async def get_gallery_info(self) -> dict | None:
        """Get gallery info including slug for public URL."""
        if not self.is_configured:
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self._api_url}/galleries/{self._gallery_id}",
                    headers=self._headers,
                )
                if resp.status_code == 200:
                    return resp.json().get("data", {})
        except Exception as e:
            logger.error("Failed to get gallery info: %s", e)
        return None

    def get_public_url(self, slug: str) -> str:
        """Build the public gallery album URL."""
        base = self._api_url.split("/api")[0]
        return f"{base}/g/{slug}"

    def get_photo_url(self, slug: str, media_id: str) -> str:
        """Build a direct photo link with download/share buttons."""
        base = self._api_url.split("/api")[0]
        return f"{base}/g/{slug}/photo/{media_id}"

    async def list_galleries(self) -> list[dict]:
        """List all galleries for this tenant."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self._api_url}/galleries",
                    headers=self._headers,
                    params={"limit": 100},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("data", [])
        except Exception as e:
            logger.error("Failed to list galleries: %s", e)
        return []

    async def create_gallery(self, name: str, slug: str = "") -> dict | None:
        """Create a new gallery."""
        try:
            body: dict = {"name": name}
            if slug:
                body["slug"] = slug
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self._api_url}/galleries",
                    headers=self._headers,
                    json=body,
                )
                if resp.status_code in (200, 201):
                    return resp.json().get("data")
                logger.error("Create gallery failed: %s", resp.text)
        except Exception as e:
            logger.error("Failed to create gallery: %s", e)
        return None

    async def publish_gallery(self, gallery_id: str) -> bool:
        """Publish a gallery so guests can view it."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.patch(
                    f"{self._api_url}/galleries/{gallery_id}",
                    headers=self._headers,
                    json={"published": True},
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error("Failed to publish gallery: %s", e)
        return False

    async def delete_gallery(self, gallery_id: str) -> bool:
        """Delete a gallery."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.delete(
                    f"{self._api_url}/galleries/{gallery_id}",
                    headers=self._headers,
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error("Failed to delete gallery: %s", e)
        return False
