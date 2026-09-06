"""Background watcher: polls the vault and emits live popup events.

Runs inside a QThread so the GUI thread stays responsive. The purely
testable scheduling decision lives in `find_due_tasks`; the thread is a thin
loop around it (addendum sections 4 & 7).
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from scheduler.config import POLL_INTERVAL_SECONDS
from scheduler.init_check import should_live_fire
from scheduler.markdown_parser import read_tasks
from scheduler.models import Task

log = logging.getLogger(__name__)


def find_due_tasks(tasks, now: datetime | None = None, grace_minutes: int = 15) -> list[Task]:
    """Tasks that should trigger a live popup at this instant (due or late)."""
    now = now or datetime.now()
    return [t for t in tasks if not t.done and should_live_fire(t, now, grace_minutes)]


class TaskWatcher(QThread):
    """Polls the today's file and emits one signal per due (or late) task."""

    fire = pyqtSignal(object)  # payload dict: {"task": Task, "late": bool}

    def __init__(self, vault: Path, poll_interval: int = POLL_INTERVAL_SECONDS, parent=None):
        super().__init__(parent)
        self._vault = Path(vault)
        self._poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def wake(self) -> None:
        """Interrupt the current sleep so the next poll runs immediately."""
        self._wake_event.set()

    def run(self) -> None:
        log.info("Watcher online — monitoring %s", self._vault)
        while not self._stop_event.is_set():
            try:
                self._poll_once()
            except Exception:  # noqa: BLE001 — the daemon must survive transient errors
                log.exception("Watcher poll iteration failed")
            self._sleep_interruptibly(self._poll_interval)

    def _poll_once(self) -> None:
        now = datetime.now()
        tasks = read_tasks(self._vault, date.today())
        for task in find_due_tasks(tasks, now):
            late = (now - task.scheduled) >= timedelta(seconds=60)
            self.fire.emit({"task": task, "late": late})

    def _sleep_interruptibly(self, seconds: int) -> None:
        self._wake_event.clear()
        deadline = time.monotonic() + seconds
        while not self._stop_event.is_set() and not self._wake_event.is_set() and time.monotonic() < deadline:
            time.sleep(0.1)