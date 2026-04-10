"""JSON template loader for photo layouts."""

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LayoutSlot:
    x: float  # fractional 0-1
    y: float
    width: float
    height: float
    rotation: float = 0.0


@dataclass
class FooterSpec:
    y: float
    height: float
    text: str = ""
    font_size: int = 24
    color: str = "#000000"


@dataclass
class LayoutTemplate:
    name: str
    width_inches: float
    height_inches: float
    dpi: int
    background: str  # hex color or image path
    slots: list[LayoutSlot] = field(default_factory=list)
    footer: FooterSpec | None = None

    @property
    def width_px(self) -> int:
        return int(self.width_inches * self.dpi)

    @property
    def height_px(self) -> int:
        return int(self.height_inches * self.dpi)


def load_template(
    name: str, templates_dir: Path | None = None
) -> LayoutTemplate:
    """Load a layout template by name from JSON file."""
    if templates_dir is None:
        templates_dir = Path(__file__).parent.parent / "static" / "templates"

    path = templates_dir / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Template not found: {name} (looked in {templates_dir})"
        )

    with open(path) as f:
        data = json.load(f)

    slots = [LayoutSlot(**s) for s in data.get("slots", [])]
    footer = FooterSpec(**data["footer"]) if "footer" in data else None

    return LayoutTemplate(
        name=data["name"],
        width_inches=data["width_inches"],
        height_inches=data["height_inches"],
        dpi=data.get("dpi", 600),
        background=data.get("background", "#ffffff"),
        slots=slots,
        footer=footer,
    )


def list_templates(templates_dir: Path | None = None) -> list[str]:
    """List available template names."""
    if templates_dir is None:
        templates_dir = Path(__file__).parent.parent / "static" / "templates"
    if not templates_dir.exists():
        return []
    return [p.stem for p in templates_dir.glob("*.json")]
