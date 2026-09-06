"""Markdown integration layer.

Reads/writes timestamped tasks inside an Obsidian-compatible vault using the
canonical `- [ ] HH:MM | description` line format (one file per day).

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
from scheduler.models import Task

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
    return replaced