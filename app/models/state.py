import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal


class BoothState(StrEnum):
    IDLE = "idle"
    CHOOSE = "choose"
    PREVIEW = "preview"
    CAPTURE = "capture"
    PROCESSING = "processing"
    REVIEW = "review"
    PRINT = "print"
    THANKYOU = "thankyou"


# Valid transitions: state -> list of allowed next states
TRANSITIONS: dict[BoothState, list[BoothState]] = {
    BoothState.IDLE:       [BoothState.CHOOSE],
    BoothState.CHOOSE:     [BoothState.PREVIEW, BoothState.IDLE],
    BoothState.PREVIEW:    [BoothState.CAPTURE, BoothState.IDLE],
    BoothState.CAPTURE:    [BoothState.PREVIEW, BoothState.PROCESSING],
    BoothState.PROCESSING: [BoothState.REVIEW],
    BoothState.REVIEW:     [
        BoothState.PRINT, BoothState.PREVIEW,
        BoothState.IDLE, BoothState.THANKYOU,
    ],
    BoothState.PRINT:      [BoothState.THANKYOU],
    BoothState.THANKYOU:   [BoothState.IDLE],
}


class InvalidTransitionError(Exception):
    def __init__(self, current: BoothState, target: BoothState):
        self.current = current
        self.target = target
        super().__init__(f"Invalid transition: {current} \u2192 {target}")


@dataclass
class CaptureSession:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    mode: Literal["photo", "gif", "boomerang"] = "photo"
    capture_count: int = 4
    captures: list[Path] = field(default_factory=list)
    selected_effect: str | None = None
    layout_template: str = "classic-4x6"
    composite_path: Path | None = None
    share_token: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
