"""Pure helpers for the month-view calendar: task counts and range coverage."""
from __future__ import annotations

import calendar as _calendar
from datetime import date

from scheduler.models import Event, Task

MONTH_CELLS = 42  # 6 weeks, Monday-first


def month_counts(tasks: list[Task]) -> dict[date, int]:
    """Pending task count per calendar day (completed tasks excluded)."""
    counts: dict[date, int] = {}
    for task in tasks:
        if task.done:
            continue
        counts[task.date] = counts.get(task.date, 0) + 1
    return counts


def range_covered_days(events: list[Event], year: int, month: int) -> set[date]:
    """Every day inside `year/month` covered by an incomplete multi-day event."""
    first = date(year, month, 1)
    last = date(year, month, _calendar.monthrange(year, month)[1])
    covered: set[date] = set()
    for event in events:
        if event.done:
            continue
        for day in event.dates():
            if first <= day <= last:
                covered.add(day)
    return covered


def month_matrix(year: int, month: int) -> list[date | None]:
    """42 Monday-first cells for the month; leading paddings are None."""
    first = date(year, month, 1)
    _, days_in_month = _calendar.monthrange(year, month)
    offset = first.weekday()  # Monday == 0
    cells: list[date | None] = [None] * offset
    cells += [date(year, month, day) for day in range(1, days_in_month + 1)]
    cells += [None] * (MONTH_CELLS - len(cells))
    return cells