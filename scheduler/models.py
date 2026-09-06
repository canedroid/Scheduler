"""Core domain models: a timestamped markdown Task, MissedTask wrapper, and range Event."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path


@dataclass
class Task:
    date: date
    time: time
    description: str
    done: bool
    source_file: Path
    source_line: str
    line_no: int

    @property
    def scheduled(self) -> datetime:
        """Wall-clock datetime this task fires at (per-day file: same calendar day)."""
        return datetime.combine(self.date, self.time)

    def task_hash(self) -> str:
        """Stable identity used to suppress refires across sessions."""
        digest = hashlib.sha1(
            f"{self.date.isoformat()}|{self.time.isoformat()}|{self.description.strip()}".encode("utf-8")
        )
        return digest.hexdigest()


def humanize_seconds(seconds: int) -> str:
    """Render a time delta like 1h 5m or 42s for the UI."""
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


@dataclass
class Event:
    """A multi-day (or range) event that spans from a start to an end instant.

    `remind_min` is the advance-notice lead: when set (via `(⏰ …)` token) it
    overrides the day-before default. `None` means "use the default lead".
    """

    start: datetime
    end: datetime
    title: str
    remind_min: int | None
    done: bool
    source_file: Path
    source_line: str
    line_no: int

    def dates(self) -> list[date]:
        """Every calendar day this event occupies, including start and end days."""
        days = (self.end.date() - self.start.date()).days
        return [self.start.date() + timedelta(days=offset) for offset in range(days + 1)]

    def event_hash(self) -> str:
        """Stable identity used to suppress repeated reminders across sessions."""
        digest = hashlib.sha1(
            f"{self.start.isoformat()}|{self.end.isoformat()}|{self.title.strip()}".encode("utf-8")
        )
        return digest.hexdigest()


@dataclass
class MissedTask:
    """An unchecked task whose scheduled time has already passed."""

    task: Task
    seconds_late: int

    @property
    def lateness(self) -> str:
        return humanize_seconds(self.seconds_late)

    @property
    def scheduled_time(self) -> str:
        return self.task.scheduled.strftime("%H:%M")