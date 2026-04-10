"""PIL-based image effects and filters.

Each function takes a PIL Image and returns a PIL Image.
"""

from PIL import Image, ImageEnhance, ImageFilter


def apply_effect(image: Image.Image, effect: str) -> Image.Image:
    """Apply a named effect to an image."""
    effects = {
        "none": _passthrough,
        "bw": _black_and_white,
        "sepia": _sepia,
        "vintage": _vintage,
        "warm": _warm,
        "cool": _cool,
        "blur": _blur,
        "sharpen": _sharpen,
        "high_contrast": _high_contrast,
    }
    fn = effects.get(effect, _passthrough)
    return fn(image)


def _passthrough(img: Image.Image) -> Image.Image:
    return img


def _black_and_white(img: Image.Image) -> Image.Image:
    return img.convert("L").convert("RGB")


def _sepia(img: Image.Image) -> Image.Image:
    bw = img.convert("L")
    sepia_r = bw.point(lambda x: min(255, int(x * 1.2)))
    sepia_g = bw.point(lambda x: min(255, int(x * 1.0)))
    sepia_b = bw.point(lambda x: min(255, int(x * 0.8)))
    return Image.merge("RGB", (sepia_r, sepia_g, sepia_b))


def _vintage(img: Image.Image) -> Image.Image:
    # Slight desaturation + warm tint + reduced contrast
    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(0.7)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(0.9)
    # Add slight warm tint by adjusting channels
    r, g, b = img.split()
    r = r.point(lambda x: min(255, int(x * 1.1)))
    b = b.point(lambda x: int(x * 0.9))
    return Image.merge("RGB", (r, g, b))


def _warm(img: Image.Image) -> Image.Image:
    r, g, b = img.split()
    r = r.point(lambda x: min(255, int(x * 1.1)))
    b = b.point(lambda x: int(x * 0.9))
    return Image.merge("RGB", (r, g, b))


def _cool(img: Image.Image) -> Image.Image:
    r, g, b = img.split()
    r = r.point(lambda x: int(x * 0.9))
    b = b.point(lambda x: min(255, int(x * 1.1)))
    return Image.merge("RGB", (r, g, b))


def _blur(img: Image.Image) -> Image.Image:
    return img.filter(ImageFilter.GaussianBlur(radius=2))


def _sharpen(img: Image.Image) -> Image.Image:
    return img.filter(ImageFilter.SHARPEN)


def _high_contrast(img: Image.Image) -> Image.Image:
    enhancer = ImageEnhance.Contrast(img)
    return enhancer.enhance(1.5)


def list_effects() -> list[str]:
    """Return names of all available effects."""
    return [
        "none",
        "bw",
        "sepia",
        "vintage",
        "warm",
        "cool",
        "blur",
        "sharpen",
        "high_contrast",
    ]
