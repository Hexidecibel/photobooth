"""Persistent photo and print counters across sessions."""

import json
import time
from datetime import datetime
from pathlib import Path


class CounterService:
    def __init__(self, data_dir: str = "data"):
        self._path = Path(data_dir) / "counters.json"
        self._start_time = time.time()
        self._counters = self._load()

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {
            "total_taken": 0,
            "total_printed": 0,
            "session_taken": 0,
            "session_printed": 0,
            "session_start": datetime.now().isoformat(),
        }

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._counters, indent=2))

    def increment_taken(self):
        self._counters["total_taken"] += 1
        self._counters["session_taken"] += 1
        self._save()

    def increment_printed(self):
        self._counters["total_printed"] += 1
        self._counters["session_printed"] += 1
        self._save()

    def reset_session(self):
        self._counters["session_taken"] = 0
        self._counters["session_printed"] = 0
        self._counters["session_start"] = datetime.now().isoformat()
        self._save()

    @property
    def counters(self) -> dict:
        return self._counters.copy()

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self._start_time
