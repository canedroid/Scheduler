"""Boot-time & live classification of schedule misses.

Implements addendum section 7's grace-window rules:

    upcoming  -> task is still in the future
    due       -> task minute was reached within the last 60s (fire live popup)
    late      -> 1s .. GRACE_MINUTES past (fire a live LATE popup)
    missed    -> beyond the grace window: only surfaced by the backlog screen

Scans NEVER mutate markdown (addendum section 2).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from scheduler.markdown_parser import read_all_tasks
from scheduler.models import MissedTask
from scheduler.config import GRACE_MINUTES

UPCOMING = "upcoming"
DUE = "due"
LATE = "late"
MISSED = "missed"


def classify(task, now: datetime | None = None, grace_minutes: int = GRACE_MINUTES) -> str:
    """Bucket a single task against the current wall-clock time."""
    now = now or datetime.now()
    delta = (now - task.scheduled).total_seconds()
    if delta < 0:
        return UPCOMING
    if delta < 60:
        return DUE
    if delta <= grace_minutes * 60:
        return LATE
    return MISSED


def should_live_fire(task, now: datetime | None = None, grace_minutes: int = GRACE_MINUTES) -> bool:
    """True when the watcher should fire a live popup for this task right now."""
    return classify(task, now, grace_minutes) in (DUE, LATE)


def aggregate_missed(
    vault: Path,
    now: datetime | None = None,
    grace_minutes: int = GRACE_MINUTES,
) -> list[MissedTask]:
    """Collect every unchecked task left in the past, oldest first.

    Returns a chronological list of MissedTask entries the backlog screen can
    present as a "SCHEDULER" review.
    """
    now = now or datetime.now()
    missed: list[MissedTask] = []
    for task in read_all_tasks(vault):
        if task.done:
            continue
        bucket = classify(task, now, grace_minutes)
        if bucket in (LATE, MISSED):
            seconds_late = int((now - task.scheduled).total_seconds())
            missed.append(MissedTask(task=task, seconds_late=seconds_late))
    missed.sort(key=lambda m: (m.task.scheduled, m.task.line_no))
    return missed