"""Main processing orchestrator: raw captures -> final composite."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from PIL import Image

from app.models.config_schema import BrandingConfig, PictureConfig
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
        branding: BrandingConfig | None = None,
    ) -> Path:
        """Full pipeline: raw captures -> final composite."""
        # Load captures
        images: list[Image.Image] = []
        for i, capture_path in enumerate(session.captures):
            img = await asyncio.to_thread(Image.open, capture_path)
            img = img.convert("RGB")

            # Per-capture effect takes priority, then session-wide effect
            effect = None
            if session.per_capture_effects and i < len(session.per_capture_effects):
                effect = session.per_capture_effects[i]
            elif session.selected_effect:
                effect = session.selected_effect

            if effect and effect != "none":
                img = await asyncio.to_thread(apply_effect, img, effect)

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

        # Composite branding logo onto the print if configured
        if branding and branding.show_on_prints:
            branding_dir = Path(__file__).parent.parent / "static" / "branding"
            logo_files = list(branding_dir.glob("logo.*"))
            if logo_files:
                try:
                    logo = await asyncio.to_thread(
                        lambda: Image.open(logo_files[0]).convert("RGBA")
                    )
                    # Scale logo to ~15% of canvas width
                    logo_w = int(composite.width * 0.15)
                    logo_h = int(logo.height * (logo_w / logo.width))
                    logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
                    # Position based on config
                    x = (composite.width - logo_w) // 2
                    if branding.logo_position == "bottom":
                        y = int(composite.height * 0.96) - logo_h
                    else:
                        y = int(composite.height * 0.02)
                    composite = composite.convert("RGBA")
                    composite.paste(logo, (x, y), logo)
                    composite = composite.convert("RGB")
                except Exception:
                    logger.warning("Failed to composite branding logo", exc_info=True)

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
