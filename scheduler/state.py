"""Persistent local state cache (plain JSON, atomic writes, thread-safe).

Tracks the accumulated penalty counter, fired-task hashes (refire suppression),
and user preferences (audio, focus behavior).
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

DEFAULTS = {
    "penalty_count": 0,
    "fired": [],
    "sound": True,
    "force_focus": False,
}


class StateStore:
    def __init__(self, path: Path, defaults: dict | None = None):
        self.path = path
        self.defaults = {**DEFAULTS, **(defaults or {})}
        self._lock = threading.RLock()
        self._data: dict = {k: (list(v) if isinstance(v, list) else v) for k, v in self.defaults.items()}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with open(self.path, encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                self._data.update({k: v for k, v in loaded.items() if k in self.defaults})
        except (json.JSONDecodeError, OSError):
            pass  # corrupt cache: fall back to defaults without crashing

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(dir=self.path.parent, prefix=".scheduler-", suffix=".json")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(self._data, handle, indent=2, sort_keys=True)
                os.replace(tmp_name, self.path)
            except OSError:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise

    # -- penalties ---------------------------------------------------------- #
    def add_penalties(self, count: int) -> int:
        with self._lock:
            self._data["penalty_count"] = max(0, self._data["penalty_count"] + int(count))
            value = self._data["penalty_count"]
        self.save()
        return value

    def reset_penalties(self) -> None:
        with self._lock:
            self._data["penalty_count"] = 0
        self.save()

    @property
    def penalty_count(self) -> int:
        with self._lock:
            return self._data["penalty_count"]

    # -- fired-task suppression --------------------------------------------- #
    def has_fired(self, task_hash: str) -> bool:
        with self._lock:
            return task_hash in self._data["fired"]

    def mark_fired(self, task_hash: str) -> None:
        with self._lock:
            if task_hash not in self._data["fired"]:
                self._data["fired"].append(task_hash)
        self.save()

    # -- preferences --------------------------------------------------------- #
    @property
    def sound(self) -> bool:
        with self._lock:
            return bool(self._data.get("sound", True))

    @sound.setter
    def sound(self, value: bool) -> None:
        with self._lock:
            self._data["sound"] = bool(value)
        self.save()

    @property
    def force_focus(self) -> bool:
        with self._lock:
            return bool(self._data.get("force_focus", False))

    @force_focus.setter
    def force_focus(self, value: bool) -> None:
        with self._lock:
            self._data["force_focus"] = bool(value)
        self.save()