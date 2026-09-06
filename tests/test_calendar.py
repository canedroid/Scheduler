"""Tests for the month-calendar pure helpers."""
from datetime import date

from scheduler.calendar import month_counts, month_matrix, range_covered_days
from scheduler.models import Task


def _task(day: date, done: bool = False) -> Task:
    return Task(
        date=day,
        time=__import__("datetime").time(9, 0),
        description="x",
        done=done,
        source_file=None,
        source_line="",
        line_no=0,
    )


def _event(start_dt, end_dt, title="Trip", done=False):
    from scheduler.models import Event

    return Event(
        start=start_dt,
        end=end_dt,
        title=title,
        remind_min=None,
        done=done,
        source_file=None,
        source_line="",
        line_no=0,
    )


def test_month_counts_pending_only():
    from datetime import datetime as dt

    tasks = [
        _task(date(2026, 9, 6)),
        _task(date(2026, 9, 6)),
        _task(date(2026, 9, 7), done=True),
        _task(date(2026, 9, 9)),
    ]
    assert month_counts(tasks) == {date(2026, 9, 6): 2, date(2026, 9, 9): 1}


def test_month_counts_empty():
    assert month_counts([]) == {}


def test_range_covered_days_intersects_month():
    from datetime import datetime as dt

    events = [
        _event(dt(2026, 8, 25, 9), dt(2026, 9, 2, 9)),   # spills into September
        _event(dt(2026, 9, 10, 9), dt(2026, 9, 11, 9), done=True),  # done -> ignored
        _event(dt(2026, 10, 1, 9), dt(2026, 10, 2, 9)),  # next month -> ignored
    ]
    covered = range_covered_days(events, 2026, 9)
    assert date(2026, 9, 1) in covered
    assert date(2026, 9, 2) in covered
    assert date(2026, 9, 10) not in covered
    assert date(2026, 9, 11) not in covered
    assert date(2026, 8, 31) not in covered
    assert date(2026, 10, 1) not in covered


def test_month_matrix_shape_and_leading_padding():
    cells = month_matrix(2026, 1)  # 1 Jan 2026 is a Thursday
    assert len(cells) == 42
    assert cells.index(date(2026, 1, 1)) == 3
    assert None in cells
    filled = [c for c in cells if c is not None]
    assert filled == [date(2026, 1, d) for d in range(1, 32)]


def test_month_matrix_monday_month():
    cells = month_matrix(2026, 9)  # 1 Sep 2026 is a Tuesday
    assert cells.index(date(2026, 9, 1)) == 1