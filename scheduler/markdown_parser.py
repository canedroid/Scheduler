"""Markdown integration layer.

Reads/writes timestamped tasks inside an Obsidian-compatible vault using the
canonical `- [ ] HH:MM | description` line format (one file per day), plus
multi-day range events:
`- [ ] 2026-09-07 09:00 → 2026-09-09 18:00 | Offsite (⏰ 1d)`.

ALL markdown writes are line-anchored (see addendum section 9): the parser
records the exact physical source line, re-reads the file before writing, and
replaces ONLY that line when it still matches. If the user has edited the file
meanwhile, the write is retried once and then aborted silently.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from pathlib import Path

from scheduler import config
from scheduler.models import Event, Task

log = logging.getLogger(__name__)

BOM = "\ufeff"


# --------------------------------------------------------------------------- #
# Reading                                                                      #
# --------------------------------------------------------------------------- #
def parse_tasks_from_file(path: Path, day: date) -> list[Task]:
    """Parse every valid task line from a single markdown file."""
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        log.warning("Unable to read %s; skipping.", path)
        return []

    tasks: list[Task] = []
    for line_no, line in enumerate(raw.splitlines()):
        match = config.TASK_LINE_RE.match(line)
        if not match:
            continue
        hour, minute = int(match.group(2)), int(match.group(3))
        if hour > 23 or minute > 59:
            continue
        description = match.group(6).strip()
        if not description:
            continue
        second = int(match.group(4) or 0)
        tasks.append(
            Task(
                date=day,
                time=time(hour, minute, second),
                description=description,
                done=match.group(1) in "xX",
                source_file=path,
                source_line=line,
                line_no=line_no,
            )
        )
    return tasks


def read_tasks(vault: Path, day: date) -> list[Task]:
    """Read tasks for one specific calendar day."""
    path = vault / config.task_filename(day)
    if not path.exists():
        return []
    return parse_tasks_from_file(path, day)


def read_all_tasks(vault: Path, now: datetime | None = None) -> list[Task]:
    """Recursively read every task whose file matches the YYYY-MM-DD.md rule."""
    del now  # reserved
    if not vault.exists():
        return []
    tasks: list[Task] = []
    for path in sorted(vault.rglob("*.md")):
        if not config.is_dated_filename(path):
            continue
        try:
            day = datetime.strptime(path.stem, config.DATE_FILE_FORMAT).date()
        except ValueError:
            continue
        tasks.extend(parse_tasks_from_file(path, day))
    return tasks


# --------------------------------------------------------------------------- #
# Reading — multi-day range events                                             #
# --------------------------------------------------------------------------- #
def parse_remind_token(text: str) -> tuple[str, int | None]:
    """Split a trailing `(⏰ Nm|Nh|Nd)` advance-notice token off a line's tail.

    Returns `(remaining_text, lead_minutes)`; lead is `None` when no token is
    present (callers then use the day-before default).
    """
    match = config.REMIND_TOKEN_RE.search(text)
    if not match:
        return text.strip(), None
    count = int(match.group(1))
    unit = match.group(2).lower()
    multiplier = {"m": 1, "h": 60, "d": 1440}[unit]
    return text[: match.start()].strip(), count * multiplier


def parse_events_from_file(path: Path, day: date) -> list[Event]:
    """Parse range-event lines from a single markdown file (day is informational)."""
    del day
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        log.warning("Unable to read %s; skipping.", path)
        return []

    events: list[Event] = []
    for line_no, line in enumerate(raw.splitlines()):
        match = config.EVENT_LINE_RE.match(line)
        if not match:
            continue
        try:
            start = datetime.strptime(f"{match.group(2)} {match.group(3)}:{match.group(4)}", "%Y-%m-%d %H:%M")
            end = datetime.strptime(f"{match.group(5)} {match.group(6)}:{match.group(7)}", "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        if end <= start:
            continue
        title, remind_min = parse_remind_token(match.group(9))
        if not title:
            continue
        events.append(
            Event(
                start=start,
                end=end,
                title=title,
                remind_min=remind_min,
                done=match.group(1) in "xX",
                source_file=path,
                source_line=line,
                line_no=line_no,
            )
        )
    return events


def read_events(vault: Path, day: date) -> list[Event]:
    """Read range events whose START day is `day` (stored in that day's file)."""
    path = vault / config.task_filename(day)
    if not path.exists():
        return []
    return parse_events_from_file(path, day)


def read_events_range(vault: Path, first: date, last: date) -> list[Event]:
    """Read events stored across every daily file in the inclusive date range."""
    events: list[Event] = []
    cursor = first
    while cursor <= last:
        events.extend(read_events(vault, cursor))
        cursor += timedelta(days=1)
    return events


def read_all_events(vault: Path) -> list[Event]:
    """Recursively read every range event across all dated files."""
    if not vault.exists():
        return []
    events: list[Event] = []
    for path in sorted(vault.rglob("*.md")):
        if not config.is_dated_filename(path):
            continue
        try:
            day = datetime.strptime(path.stem, config.DATE_FILE_FORMAT).date()
        except ValueError:
            continue
        events.extend(parse_events_from_file(path, day))
    return events


# --------------------------------------------------------------------------- #
# Writing (line-anchored, conflict-safe)                                       #
# --------------------------------------------------------------------------- #
def _read_lines_with_endings(path: Path) -> list[str] | None:
    """Return raw lines preserving endings; None when unreadable."""
    try:
        text = path.read_text(encoding="utf-8-sig").replace(BOM, "")
        lines = text.splitlines(keepends=True)
    except (OSError, UnicodeDecodeError):
        log.warning("Unable to read %s; aborting write.", path)
        return None
    if lines and not lines[-1].endswith(("\n", "\r")):
        lines[-1] += "\n"
    return lines


def _write_lines(path: Path, lines: list[str]) -> bool:
    try:
        path.write_text("".join(lines), encoding="utf-8")
        return True
    except OSError:
        log.exception("Unable to write %s.", path)
        return False


def _replace_anchored_line(path: Path, anchor: str, new_line: str, retries: int = 1) -> bool:
    """Line-anchor write: replace ONLY the physical line equal to `anchor`."""
    anchor = anchor.rstrip("\r\n")
    for _ in range(max(1, retries)):
        lines = _read_lines_with_endings(path)
        if lines is None:
            return False
        for index, raw_line in enumerate(lines):
            if raw_line.rstrip("\r\n") == anchor:
                lines[index] = new_line.rstrip("\r\n") + "\n"
                return _write_lines(path, lines)
    log.info("Anchor line not found in %s; aborting to preserve user edits.", path)
    return False


def _unchecked_task(task: Task) -> bool:
    return not task.done


def complete_task(vault: Path, task: Task) -> bool:
    """Rewrite `- [ ]` -> `- [x]` for the exact task line. No-op if already done."""
    if not _unchecked_task(task):
        return False
    new_line = config.CHECKBOX_COMPLETE_RE.sub(r"\1[x]", task.source_line)
    if new_line == task.source_line:
        return False
    replaced = _replace_anchored_line(task.source_file, task.source_line, new_line)
    if replaced:
        task.done = True
    return replaced


def snooze_task(vault: Path, task: Task, minutes: int) -> bool:
    """Rewrite the task's HH:MM forward by `minutes` on its exact source line."""
    match = config.CHECKBOX_SNOOZE_RE.match(task.source_line)
    if not match:
        return False
    new_dt: datetime = task.scheduled + timedelta(minutes=minutes)
    new_time = new_dt.strftime("%H:%M")
    new_line = f"{match.group(1)} {new_time}{match.group(5)}"
    replaced = _replace_anchored_line(task.source_file, task.source_line, new_line)
    if replaced:
        task.time = new_dt.time()
        task.source_line = new_line
    return replaced


def reschedule_task(vault: Path, task: Task, new_time: time) -> bool:
    """Set a task to an explicit new HH:MM (used by the planner's time picker)."""
    del vault
    match = config.CHECKBOX_SNOOZE_RE.match(task.source_line)
    if not match:
        return False
    if new_time.hour > 23 or new_time.minute > 59:
        return False
    new_line = f"{match.group(1)} {new_time:%H:%M}{match.group(5)}"
    replaced = _replace_anchored_line(task.source_file, task.source_line, new_line)
    if replaced:
        task.time = new_time
        task.source_line = new_line
    return replaced


# --------------------------------------------------------------------------- #
# Adding / removing tasks                                                      #
# --------------------------------------------------------------------------- #
def _task_line(time_value: time, description: str) -> str:
    return f"- [ ] {time_value:%H:%M} | {description}"


def add_task(vault: Path, day, task_time: time, description: str) -> bool:
    """Append `- [ ] HH:MM | description` to the day's file (created if missing)."""
    description = description.strip()
    if not description or task_time.hour > 23 or task_time.minute > 59:
        return False
    path = vault / config.task_filename(day)
    if path.exists():
        lines = _read_lines_with_endings(path)
        if lines is None:
            return False
    else:
        lines = [f"# {day:{config.DATE_FILE_FORMAT}}\n"]
    lines.append(_task_line(task_time, description) + "\n")
    return _write_lines(path, lines)


def delete_task(vault: Path, task: Task) -> bool:
    """Remove only the exact anchored source line (aborts if the line changed)."""
    del vault
    lines = _read_lines_with_endings(task.source_file)
    if lines is None:
        return False
    anchor = task.source_line.rstrip("\r\n")
    for index, raw_line in enumerate(lines):
        if raw_line.rstrip("\r\n") == anchor:
            del lines[index]
            return _write_lines(task.source_file, lines)
    log.info("Delete anchor not found in %s; aborting to preserve user edits.", task.source_file)
    return False


# --------------------------------------------------------------------------- #
# Events — writing (line-anchored, conflict-safe)                              #
# --------------------------------------------------------------------------- #
def _event_token(minutes: int | None) -> str:
    """Render `remind_min` back into its `(⏰ …)` token; None renders nothing."""
    if minutes is None:
        return ""
    if minutes and minutes % 1440 == 0:
        return f" (⏰ {minutes // 1440}d)"
    if minutes and minutes % 60 == 0:
        return f" (⏰ {minutes // 60}h)"
    return f" (⏰ {minutes}m)"


def _event_line(start: datetime, end: datetime, title: str, remind_min: int | None) -> str:
    cleaned_title = title.strip()
    if not cleaned_title:
        raise ValueError("event title must not be empty")
    return f"- [ ] {start:%Y-%m-%d %H:%M} → {end:%Y-%m-%d %H:%M} | {cleaned_title}{_event_token(remind_min)}"


def add_event(
    vault: Path,
    start: datetime,
    end: datetime,
    title: str,
    remind_min: int | None = None,
) -> bool:
    """Append a range-event line into the START-day's file (created if missing)."""
    if end <= start:
        return False
    title = title.strip()
    if not title:
        return False
    path = vault / config.task_filename(start.date())
    if path.exists():
        lines = _read_lines_with_endings(path)
        if lines is None:
            return False
    else:
        lines = [f"# {start.date():{config.DATE_FILE_FORMAT}}\n"]
    lines.append(_event_line(start, end, title, remind_min) + "\n")
    return _write_lines(path, lines)


def complete_event(vault: Path, event: Event) -> bool:
    """Flip the event line's checkbox `- [ ]` -> `- [x]`. No-op if already done."""
    del vault
    if event.done:
        return False
    new_line = config.CHECKBOX_COMPLETE_RE.sub(r"\1[x]", event.source_line)
    if new_line == event.source_line:
        return False
    replaced = _replace_anchored_line(event.source_file, event.source_line, new_line)
    if replaced:
        event.done = True
    return replaced


def delete_event(vault: Path, event: Event) -> bool:
    """Remove only the exact anchored event line (aborts if the line changed)."""
    del vault
    lines = _read_lines_with_endings(event.source_file)
    if lines is None:
        return False
    anchor = event.source_line.rstrip("\r\n")
    for index, raw_line in enumerate(lines):
        if raw_line.rstrip("\r\n") == anchor:
            del lines[index]
            return _write_lines(event.source_file, lines)
    log.info("Delete anchor not found in %s; aborting to preserve user edits.", event.source_file)
    return False