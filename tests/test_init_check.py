from datetime import date, datetime, timedelta

from scheduler.init_check import (
    DUE,
    LATE,
    MISSED,
    UPCOMING,
    aggregate_missed,
    classify,
    should_live_fire,
)
from scheduler.models import Task, MissedTask


def _make_task(day, hh_mm, desc="- [ ] 07:00 | X", done=False):
    h, m = map(int, hh_mm.split(":"))
    return Task(
        date=day,
        time=__import__("datetime").time(h, m),
        description=desc.partition("|")[2].strip() or "X",
        done=done,
        source_file=None,
        source_line=desc,
        line_no=0,
    )


DAY = date(2026, 9, 6)


def test_classify_boundaries():
    at_7 = datetime(2026, 9, 6, 7, 0, 0)
    task = _make_task(DAY, "07:00")

    assert classify(task, at_7) == DUE  # exact minute
    assert classify(task, at_7 + timedelta(seconds=59)) == DUE
    assert classify(task, at_7 + timedelta(seconds=60)) == LATE
    assert classify(task, at_7 + timedelta(minutes=15)) == LATE  # grace inclusive
    assert classify(task, at_7 + timedelta(minutes=15, seconds=1)) == MISSED
    assert classify(task, at_7 + timedelta(hours=26)) == MISSED
    assert classify(task, at_7 - timedelta(seconds=1)) == UPCOMING


def test_should_live_fire_within_grace():
    at = datetime(2026, 9, 6, 7, 12, 0)
    task = _make_task(DAY, "07:00")
    assert should_live_fire(task, at) is True  # 12 min late -> live LATE popup
    task2 = _make_task(DAY, "07:00")
    assert should_live_fire(task2, at + timedelta(minutes=15, seconds=1)) is False
    assert should_live_fire(_make_task(DAY, "07:00"), at - timedelta(hours=1)) is False


def _write(vault, name, content):
    path = vault / name
    path.write_text(content, encoding="utf-8")
    return path


def test_aggregate_missed(today_vault):
    now = datetime(2026, 9, 6, 14, 30, 0)
    _write(
        today_vault,
        "2026-09-06.md",
        "\n".join(
            [
                "- [ ] 08:00 | Missed morning",
                "- [x] 09:00 | Done on time",
                "- [ ] 14:29 | One minute ago (late, still live-firable)",
                "- [ ] 16:00 | Later today, not missed",
            ]
        )
        + "\n",
    )
    _write(today_vault, "2026-09-05.md", "- [ ] 22:00 | Yesterday missed\n")
    _write(today_vault, "2026-09-07.md", "- [ ] 06:00 | Tomorrow, never late\n")

    missed = aggregate_missed(today_vault, now)
    assert [q.task.description for q in missed] == [
        "Yesterday missed",
        "Missed morning",
        "One minute ago (late, still live-firable)",
    ]
    assert all(q.seconds_late > 0 for q in missed)
    first, _, last = missed
    assert first.scheduled_time == "22:00"
    assert last.scheduled_time == "14:29"  # chronological order, next-task-after
    assert last.lateness == "1m 0s"


def test_aggregate_skips_done_and_upcoming(today_vault):
    now = datetime(2026, 9, 6, 10, 0, 0)
    _write(today_vault, "2026-09-06.md", "- [x] 08:00 | Done\n- [ ] 12:00 | Later\n")
    assert aggregate_missed(today_vault, now) == []


def test_aggregate_recurses_into_nested(today_vault):
    now = datetime(2026, 9, 6, 10, 0, 0)
    (today_vault / "projects").mkdir()
    _write(today_vault, "projects/2026-09-05.md", "- [ ] 09:00 | Nested miss\n")
    _write(today_vault, "projects/notes.md", "- [ ] 08:00 | Not date-named\n")
    missed = aggregate_missed(today_vault, now)
    assert [q.task.description for q in missed] == ["Nested miss"]
    assert isinstance(missed[0], MissedTask)