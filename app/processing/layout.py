"""Layout engine that composes captures into a final print-ready image."""

import glob
import logging
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.processing.templates import ImageOverlay, LayoutTemplate, TextOverlay

logger = logging.getLogger(__name__)


class LayoutEngine:
    def compose(
        self,
        captures: list[Image.Image],
        template: LayoutTemplate,
        footer_vars: dict[str, str] | None = None,
    ) -> Image.Image:
        """Compose captures into a layout using the template."""
        canvas = self._create_canvas(template)
        self._place_captures(canvas, captures, template)

        # Draw text overlays
        variables = footer_vars or {}
        for overlay in template.text_overlays:
            self._draw_text_overlay(canvas, overlay, template, variables)

        # Draw image overlays (on top of everything except footer)
        for overlay in template.image_overlays:
            self._draw_image_overlay(canvas, overlay, template)

        if template.footer:
            self._draw_footer(canvas, template, variables)
        return canvas

    def _create_canvas(self, template: LayoutTemplate) -> Image.Image:
        """Create the background canvas."""
        w, h = template.width_px, template.height_px
        if template.background.startswith("#"):
            color = self._hex_to_rgb(template.background)
            return Image.new("RGB", (w, h), color)
        elif Path(template.background).exists():
            bg = Image.open(template.background).convert("RGB")
            return bg.resize((w, h), Image.LANCZOS)
        else:
            return Image.new("RGB", (w, h), (255, 255, 255))

    def _place_captures(
        self,
        canvas: Image.Image,
        captures: list[Image.Image],
        template: LayoutTemplate,
    ) -> None:
        """Place captures into template slots."""
        for i, slot in enumerate(template.slots):
            if i >= len(captures):
                break
            capture = captures[i]

            # Calculate pixel positions from fractional coords
            sx = int(slot.x * canvas.width)
            sy = int(slot.y * canvas.height)
            sw = int(slot.width * canvas.width)
            sh = int(slot.height * canvas.height)

            # Resize capture to fit slot, preserving aspect ratio
            resized = self._fit_to_slot(capture, sw, sh)

            # Center in slot
            offset_x = sx + (sw - resized.width) // 2
            offset_y = sy + (sh - resized.height) // 2

            # Add subtle border around photo for depth
            border_img = Image.new("RGB", (resized.width + 2, resized.height + 2),
                                   self._hex_to_rgb("#d0d0d0"))
            border_img.paste(resized, (1, 1))
            resized = border_img
            offset_x = sx + (sw - resized.width) // 2
            offset_y = sy + (sh - resized.height) // 2

            # Apply rotation if specified
            if slot.rotation:
                resized = resized.rotate(
                    -slot.rotation, expand=True, resample=Image.BICUBIC
                )

            canvas.paste(resized, (offset_x, offset_y))

    def _fit_to_slot(
        self, image: Image.Image, slot_w: int, slot_h: int
    ) -> Image.Image:
        """Resize and crop image to fill slot completely (no letterboxing)."""
        img_ratio = image.width / image.height
        slot_ratio = slot_w / slot_h

        if img_ratio > slot_ratio:
            # Image is wider than slot -- fit to height, crop sides
            new_h = slot_h
            new_w = int(slot_h * img_ratio)
        else:
            # Image is taller than slot -- fit to width, crop top/bottom
            new_w = slot_w
            new_h = int(slot_w / img_ratio)

        resized = image.resize((new_w, new_h), Image.LANCZOS)

        # Center-crop to exact slot dimensions
        left = (new_w - slot_w) // 2
        top = (new_h - slot_h) // 2
        return resized.crop((left, top, left + slot_w, top + slot_h))

    def _draw_text_overlay(
        self,
        canvas: Image.Image,
        overlay: TextOverlay,
        template: LayoutTemplate,
        variables: dict[str, str],
    ) -> None:
        """Draw a text overlay on the canvas."""
        # Replace variables
        text = overlay.text
        variables.setdefault("date", datetime.now().strftime("%Y-%m-%d"))
        variables.setdefault("event_name", "Photo Booth")
        for key, val in variables.items():
            text = text.replace(f"{{{key}}}", val)

        # Load font
        font_size = int(overlay.font_size * template.dpi / 72)
        font = None
        if overlay.font:
            for font_dir in [
                "/usr/share/fonts/truetype",
                "/usr/share/fonts/opentype",
            ]:
                matches = glob.glob(
                    f"{font_dir}/**/*{overlay.font}*",
                    recursive=True,
                )
                if matches:
                    font = ImageFont.truetype(matches[0], font_size)
                    break
        if not font:
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    font_size,
                )
            except (OSError, IOError):
                font = ImageFont.load_default()

        # Calculate text dimensions
        draw = ImageDraw.Draw(canvas)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        x = int(overlay.x * canvas.width)
        y = int(overlay.y * canvas.height)

        # Alignment
        if overlay.align == "center":
            x -= text_w // 2
        elif overlay.align == "right":
            x -= text_w

        # Handle rotation -- draw on transparent layer, rotate, paste
        if overlay.rotation:
            txt_layer = Image.new(
                "RGBA", (text_w + 20, text_h + 20), (0, 0, 0, 0)
            )
            txt_draw = ImageDraw.Draw(txt_layer)
            color = self._hex_to_rgb(overlay.color)
            alpha = int(overlay.opacity * 255)
            txt_draw.text((10, 10), text, fill=(*color, alpha), font=font)
            txt_layer = txt_layer.rotate(
                -overlay.rotation, expand=True, resample=Image.BICUBIC
            )
            canvas_rgba = canvas.convert("RGBA")
            canvas_rgba.paste(txt_layer, (x, y), txt_layer)
            canvas.paste(canvas_rgba.convert("RGB"))
        else:
            color = self._hex_to_rgb(overlay.color)
            if overlay.opacity < 1.0:
                # Draw on transparent layer for opacity support
                txt_layer = Image.new(
                    "RGBA", canvas.size, (0, 0, 0, 0)
                )
                txt_draw = ImageDraw.Draw(txt_layer)
                alpha = int(overlay.opacity * 255)
                txt_draw.text((x, y), text, fill=(*color, alpha), font=font)
                canvas_rgba = canvas.convert("RGBA")
                canvas_rgba = Image.alpha_composite(canvas_rgba, txt_layer)
                canvas.paste(canvas_rgba.convert("RGB"))
            else:
                draw.text((x, y), text, fill=color, font=font)

    def _draw_image_overlay(
        self,
        canvas: Image.Image,
        overlay: ImageOverlay,
        template: LayoutTemplate,
    ) -> None:
        """Draw an image overlay (PNG with transparency) on the canvas."""
        # Look for the overlay image
        overlay_path = (
            Path(__file__).parent.parent / "static" / "overlays" / overlay.src
        )
        if not overlay_path.exists():
            # Try as absolute or relative path
            overlay_path = Path(overlay.src)
            if not overlay_path.exists():
                logger.warning("Overlay image not found: %s", overlay.src)
                return

        img = Image.open(overlay_path).convert("RGBA")

        # Calculate size and position
        ow = int(overlay.width * canvas.width)
        oh = int(overlay.height * canvas.height)
        ox = int(overlay.x * canvas.width)
        oy = int(overlay.y * canvas.height)

        img = img.resize((ow, oh), Image.LANCZOS)

        # Apply opacity
        if overlay.opacity < 1.0:
            alpha = img.split()[3]
            alpha = alpha.point(lambda p: int(p * overlay.opacity))
            img.putalpha(alpha)

        # Rotation
        if overlay.rotation:
            img = img.rotate(
                -overlay.rotation, expand=True, resample=Image.BICUBIC
            )

        # Paste with transparency
        canvas_rgba = canvas.convert("RGBA")
        canvas_rgba.paste(img, (ox, oy), img)
        canvas.paste(canvas_rgba.convert("RGB"))

    def _draw_footer(
        self,
        canvas: Image.Image,
        template: LayoutTemplate,
        variables: dict[str, str],
    ) -> None:
        """Draw footer text on the canvas."""
        if not template.footer:
            return

        footer = template.footer
        text = footer.text

        # Replace variables
        variables.setdefault("date", datetime.now().strftime("%Y-%m-%d"))
        variables.setdefault("event_name", "Photo Booth")
        for key, val in variables.items():
            text = text.replace(f"{{{key}}}", val)

        draw = ImageDraw.Draw(canvas)

        # Try to load a font, fall back to default
        try:
            font_size = int(footer.font_size * template.dpi / 72)
            # Try template-specified font first, then fallback
            font = None
            if footer.font:
                for font_dir in [
                    "/usr/share/fonts/truetype",
                    "/usr/share/fonts/opentype",
                ]:
                    matches = glob.glob(
                        f"{font_dir}/**/*{footer.font}*",
                        recursive=True,
                    )
                    if matches:
                        font = ImageFont.truetype(matches[0], font_size)
                        break
            if not font:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    font_size,
                )
        except (OSError, IOError):
            font = ImageFont.load_default()

        color = self._hex_to_rgb(footer.color)

        # Center text in footer area
        fy = int(footer.y * canvas.height)
        fh = int(footer.height * canvas.height)

        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        tx = (canvas.width - text_w) // 2
        ty = fy + (fh - text_h) // 2

        draw.text((tx, ty), text, fill=color, font=font)

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple[int, ...]:
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
