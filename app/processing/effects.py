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
        "cartoon": _cartoon,
        "pencil_sketch": _pencil_sketch,
        "watercolor": _watercolor,
        "pop_art": _pop_art,
        "oil_painting": _oil_painting,
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


def _cartoon(img: Image.Image) -> Image.Image:
    """Comic book / cartoon effect using edge detection + bilateral filter."""
    try:
        import cv2
        import numpy as np

        arr = np.array(img)
        # Convert to BGR for OpenCV
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        # Downsample for speed, apply bilateral filter, upsample
        small = cv2.pyrDown(bgr)
        for _ in range(7):
            small = cv2.bilateralFilter(small, 9, 9, 7)
        smooth = cv2.pyrUp(small)
        # Ensure same size after pyrUp/pyrDown
        smooth = cv2.resize(smooth, (bgr.shape[1], bgr.shape[0]))
        # Edge detection
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        blur = cv2.medianBlur(gray, 7)
        edges = cv2.adaptiveThreshold(
            blur, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 9, 2
        )
        # Combine: smooth color + bold edges
        edges_rgb = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        cartoon = cv2.bitwise_and(smooth, edges_rgb)
        # Back to RGB PIL
        return Image.fromarray(cv2.cvtColor(cartoon, cv2.COLOR_BGR2RGB))
    except ImportError:
        # Fallback: just do a strong posterize + edge enhance with PIL
        img = img.quantize(colors=8, method=2).convert("RGB")
        return img.filter(ImageFilter.EDGE_ENHANCE_MORE)


def _pencil_sketch(img: Image.Image) -> Image.Image:
    """Pencil sketch effect -- grayscale with pencil-drawn edges."""
    try:
        import cv2
        import numpy as np

        arr = np.array(img)
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        # Invert
        inv = cv2.bitwise_not(gray)
        # Gaussian blur the inverted image
        blur = cv2.GaussianBlur(inv, (21, 21), 0)
        # Blend: divide gray by inverted blur
        sketch = cv2.divide(gray, cv2.bitwise_not(blur), scale=256.0)
        # Convert to RGB PIL
        return Image.fromarray(cv2.cvtColor(sketch, cv2.COLOR_GRAY2RGB))
    except ImportError:
        # Fallback: PIL contour
        gray = img.convert("L")
        return gray.filter(ImageFilter.CONTOUR).convert("RGB")


def _watercolor(img: Image.Image) -> Image.Image:
    """Watercolor painting effect -- soft edges with vibrant colors."""
    try:
        import cv2
        import numpy as np

        arr = np.array(img)
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        # Heavy bilateral filtering for watercolor smoothness
        filtered = bgr
        for _ in range(3):
            filtered = cv2.bilateralFilter(filtered, 9, 75, 75)
        # Boost saturation slightly
        hsv = cv2.cvtColor(filtered, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.3, 0, 255)
        hsv = hsv.astype(np.uint8)
        result = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        return Image.fromarray(cv2.cvtColor(result, cv2.COLOR_BGR2RGB))
    except ImportError:
        # Fallback: PIL smooth + color boost
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1.3)
        return img.filter(ImageFilter.SMOOTH_MORE)


def _pop_art(img: Image.Image) -> Image.Image:
    """Pop art effect -- high contrast, posterized colors like Warhol."""
    try:
        import cv2
        import numpy as np

        arr = np.array(img)
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        # Posterize: reduce color depth
        div = 64
        bgr = (bgr // div) * div + div // 2
        # Boost saturation
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 2.0, 0, 255)
        hsv[:, :, 2] = np.clip(hsv[:, :, 2] * 1.2, 0, 255)
        hsv = hsv.astype(np.uint8)
        result = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        return Image.fromarray(cv2.cvtColor(result, cv2.COLOR_BGR2RGB))
    except ImportError:
        img = img.quantize(colors=6, method=2).convert("RGB")
        enhancer = ImageEnhance.Color(img)
        return enhancer.enhance(2.0)


def _oil_painting(img: Image.Image) -> Image.Image:
    """Oil painting effect -- thick brush strokes look."""
    try:
        import cv2
        import numpy as np

        arr = np.array(img)
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        # OpenCV's stylization function gives an oil painting look
        result = cv2.stylization(bgr, sigma_s=60, sigma_r=0.6)
        return Image.fromarray(cv2.cvtColor(result, cv2.COLOR_BGR2RGB))
    except (ImportError, AttributeError):
        # Fallback: heavy smooth
        for _ in range(3):
            img = img.filter(ImageFilter.SMOOTH_MORE)
        enhancer = ImageEnhance.Color(img)
        return enhancer.enhance(1.2)


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
        "cartoon",
        "pencil_sketch",
        "watercolor",
        "pop_art",
        "oil_painting",
    ]
