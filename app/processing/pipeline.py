"""Main processing orchestrator: raw captures -> final composite."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from PIL import Image

from app.models.config_schema import PictureConfig
from app.models.state import CaptureSession
from app.processing.effects import apply_effect
from app.processing.layout import LayoutEngine
from app.processing.templates import load_template

logger = logging.getLogger(__name__)


class ProcessingPipeline:
    def __init__(self) -> None:
        self._layout_engine = LayoutEngine()

    async def process(
        self,
        session: CaptureSession,
        config: PictureConfig,
        footer_vars: dict[str, str] | None = None,
        save_dir: str = "data",
    ) -> Path:
        """Full pipeline: raw captures -> final composite."""
        # Load captures
        images: list[Image.Image] = []
        for capture_path in session.captures:
            img = await asyncio.to_thread(Image.open, capture_path)
            img = img.convert("RGB")

            # Apply selected effect
            if session.selected_effect and session.selected_effect != "none":
                img = await asyncio.to_thread(
                    apply_effect, img, session.selected_effect
                )

            images.append(img)

        # Load template and compose
        template = load_template(session.layout_template)
        composite = await asyncio.to_thread(
            self._layout_engine.compose, images, template, footer_vars
        )

        # Apply overlay if configured
        if config.overlay_path:
            overlay_file = Path(config.overlay_path)
            if overlay_file.exists():
                overlay = await asyncio.to_thread(
                    lambda: Image.open(overlay_file).convert("RGBA")
                )
                overlay = overlay.resize(composite.size, Image.LANCZOS)
                composite = composite.convert("RGBA")
                composite = Image.alpha_composite(composite, overlay)
                composite = composite.convert("RGB")

        # Save
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_dir = Path(save_dir) / "photos" / date_str
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{session.id}.jpg"

        await asyncio.to_thread(
            composite.save, str(output_path), "JPEG", quality=95
        )

        session.composite_path = output_path
        logger.info("Composite saved: %s", output_path)
        return output_path
