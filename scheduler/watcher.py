"""Background watcher: polls the vault and emits live popup events.

Runs inside a QThread so the GUI thread stays responsive. The purely
testable scheduling decisions live in `find_due_tasks` and
`find_event_reminders`; the thread is a thin loop around them
(addendum sections 4 & 7).
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from scheduler.config import EVENT_MAX_LEAD_DAYS, EVENT_REMIND_DEFAULT_MIN, POLL_INTERVAL_SECONDS
from scheduler.init_check import should_live_fire
from scheduler.markdown_parser import read_events_range, read_tasks
from scheduler.models import Event, Task

log = logging.getLogger(__name__)


def find_due_tasks(tasks, now: datetime | None = None, grace_minutes: int = 15) -> list[Task]:
    """Tasks that should trigger a live popup at this instant (due or late)."""
    now = now or datetime.now()
    return [t for t in tasks if not t.done and should_live_fire(t, now, grace_minutes)]


def find_event_reminders(
    events: list[Event],
    now: datetime | None = None,
    default_lead_min: int = EVENT_REMIND_DEFAULT_MIN,
) -> list[tuple[Event, int]]:
    """Events inside their advance-notice window (not yet started, not done).

    Returns `(event, lead_minutes)` pairs. When an event carries no `(⏰ …)`
    token, `default_lead_min` governs; only the window
    `[start - lead, start)` counts, so each event reminds exactly once.
    """
    now = now or datetime.now()
    reminders: list[tuple[Event, int]] = []
    for event in events:
        if event.done:
            continue
        lead = event.remind_min if event.remind_min is not None else default_lead_min
        if lead <= 0:
            continue
        window_start = event.start - timedelta(minutes=lead)
        if window_start <= now < event.start:
            reminders.append((event, lead))
    return reminders


class TaskWatcher(QThread):
    """Polls the vault and emits one signal per due (or late) task or event reminder."""

    fire = pyqtSignal(object)  # payload dict: {"task": Task, "late": bool}
    eventRemind = pyqtSignal(object)  # payload dict: {"event": Event, "lead": int}

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

        today = date.today()
        horizon = today + timedelta(days=EVENT_MAX_LEAD_DAYS)
        events = read_events_range(self._vault, today, horizon)
        for event, lead in find_event_reminders(events, now):
            self.eventRemind.emit({"event": event, "lead": lead})

    def _sleep_interruptibly(self, seconds: int) -> None:
        self._wake_event.clear()
        deadline = time.monotonic() + seconds
        while not self._stop_event.is_set() and not self._wake_event.is_set() and time.monotonic() < deadline:
            time.sleep(0.1)