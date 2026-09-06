"""Tests for the multi-day range-event layer (parse / add / delete / complete)."""
from datetime import date, datetime

from scheduler.markdown_parser import (
    add_event,
    complete_event,
    delete_event,
    parse_events_from_file,
    parse_remind_token,
    read_events,
    read_events_range,
    read_all_events,
)
from scheduler.models import Event


def _write(vault, day: date, *lines):
    path = vault / f"{day:%Y-%m-%d}.md"
    path.write_text(f"# {day:%Y-%m-%d}\n" + "".join(lines), encoding="utf-8")
    return path


EVENT_LINE = "- [ ] 2026-09-07 09:00 → 2026-09-09 18:00 | Exams (⏰ 1d)\n"


# --------------------------------------------------------------------------- #
# token parsing                                                                #
# --------------------------------------------------------------------------- #
def test_parse_remind_token_variants():
    assert parse_remind_token("Exams (⏰ 1d)") == ("Exams", 1440)
    assert parse_remind_token("Pickup (⏰ 10m)") == ("Pickup", 10)
    assert parse_remind_token("Call (⏰ 2h)") == ("Call", 120)
    assert parse_remind_token("Plain") == ("Plain", None)
    assert parse_remind_token("  padded\t(⏰ 30m)  ") == ("padded", 30)


def test_parse_event_line_fields(tmp_path):
    _write(tmp_path, date(2026, 9, 7), EVENT_LINE)
    events = parse_events_from_file(tmp_path / "2026-09-07.md", date(2026, 9, 7))
    assert len(events) == 1
    event = events[0]
    assert event.start == datetime(2026, 9, 7, 9, 0)
    assert event.end == datetime(2026, 9, 9, 18, 0)
    assert event.title == "Exams"
    assert event.remind_min == 1440
    assert event.done is False


def test_parse_events_skips_tasks_and_invalid_ranges(tmp_path):
    text = (
        "# 2026-09-07\n"
        "- [ ] 09:00 | normal task\n"
        "- [ ] 2026-09-07 09:00 → 2026-09-07 08:00 | end before start\n"
        "- [ ] 2026-13-07 09:00 → 2026-09-08 09:00 | bad date\n"
        "- [x] 2026-09-07 09:00 → 2026-09-08 09:00 | Done trip (⏰ 30m)\n"
        f"{EVENT_LINE}"
    )
    path = tmp_path / "2026-09-07.md"
    path.write_text(text, encoding="utf-8")
    events = parse_events_from_file(path, date(2026, 9, 7))
    assert [e.title for e in events] == ["Done trip", "Exams"]
    assert events[0].done is True and events[0].remind_min == 30


def test_event_dates_spreads_range(tmp_path):
    path = tmp_path / "2026-09-07.md"
    path.write_text(EVENT_LINE, encoding="utf-8")
    event = parse_events_from_file(path, date(2026, 9, 7))[0]
    assert event.dates() == [
        date(2026, 9, 7),
        date(2026, 9, 8),
        date(2026, 9, 9),
    ]


# --------------------------------------------------------------------------- #
# reads                                                                         #
# --------------------------------------------------------------------------- #
def test_read_events_is_start_day_scoped(tmp_path):
    _write(tmp_path, date(2026, 9, 7), EVENT_LINE)
    _write(
        tmp_path,
        date(2026, 9, 8),
        "- [ ] 2026-09-08 10:00 → 2026-09-09 12:00 | Other\n",
    )
    assert [e.title for e in read_events(tmp_path, date(2026, 9, 7))] == ["Exams"]
    assert [e.title for e in read_events(tmp_path, date(2026, 9, 8))] == ["Other"]
    assert read_events(tmp_path, date(2026, 9, 9)) == []


def test_read_events_range_spans_future_files(tmp_path):
    _write(tmp_path, date(2026, 9, 8), "- [ ] 2026-09-10 09:00 → 2026-09-11 09:00 | Trip\n")
    events = read_events_range(
        tmp_path,
        date(2026, 9, 7),
        date(2026, 9, 10),
    )
    assert [e.title for e in events] == ["Trip"]


def test_read_all_events_recurses(tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    _write(nested, date(2026, 9, 9), "- [ ] 2026-09-09 09:00 → 2026-09-09 11:00 | Deep\n")
    assert [e.title for e in read_all_events(tmp_path)] == ["Deep"]


# --------------------------------------------------------------------------- #
# writes                                                                         #
# --------------------------------------------------------------------------- #
def test_add_event_writes_into_start_day_file(tmp_path):
    assert add_event(
        tmp_path,
        datetime(2026, 9, 7, 9, 0),
        datetime(2026, 9, 9, 18, 0),
        "Exams",
    )
    content = (tmp_path / "2026-09-07.md").read_text(encoding="utf-8")
    assert "- [ ] 2026-09-07 09:00 → 2026-09-09 18:00 | Exams\n" in content


def test_add_event_with_token_round_trips(tmp_path):
    assert add_event(
        tmp_path,
        datetime(2026, 9, 8, 10, 30),
        datetime(2026, 9, 8, 12, 0),
        "Pickup",
        remind_min=10,
    )
    event = read_events(tmp_path, date(2026, 9, 8))[0]
    assert event.title == "Pickup"
    assert event.remind_min == 10
    assert "(⏰ 10m)" in (tmp_path / "2026-09-08.md").read_text(encoding="utf-8")


def test_add_event_validates_range_and_title(tmp_path):
    assert not add_event(
        tmp_path,
        datetime(2026, 9, 9, 10, 0),
        datetime(2026, 9, 9, 9, 0),
        "Bad",
    )
    assert not add_event(
        tmp_path,
        datetime(2026, 9, 9, 10, 0),
        datetime(2026, 9, 10, 9, 0),
        "   ",
    )
    assert read_all_events(tmp_path) == []


def test_complete_event_flips_checkbox(tmp_path):
    _write(tmp_path, date(2026, 9, 7), EVENT_LINE)
    event = read_events(tmp_path, date(2026, 9, 7))[0]
    assert complete_event(tmp_path, event)
    content = (tmp_path / "2026-09-07.md").read_text(encoding="utf-8")
    assert "- [x] 2026-09-07 09:00 → 2026-09-09 18:00 | Exams (⏰ 1d)\n" in content
    assert event.done is True
    assert not complete_event(tmp_path, event)


def test_delete_event_anchored(tmp_path):
    _write(tmp_path, date(2026, 9, 7), EVENT_LINE)
    event = read_events(tmp_path, date(2026, 9, 7))[0]
    assert delete_event(tmp_path, event)
    assert read_events(tmp_path, date(2026, 9, 7)) == []


def test_delete_event_aborts_when_line_edited(tmp_path):
    path = _write(tmp_path, date(2026, 9, 7), EVENT_LINE)
    event = read_events(tmp_path, date(2026, 9, 7))[0]
    path.write_text(
        path.read_text(encoding="utf-8").replace("Exams (⏰ 1d)", "Changed in Obsidian"),
        encoding="utf-8",
    )
    assert not delete_event(tmp_path, event)


def test_event_hash_stable(tmp_path):
    _write(tmp_path, date(2026, 9, 7), EVENT_LINE)
    event_a = read_events(tmp_path, date(2026, 9, 7))[0]
    event_b = read_events(tmp_path, date(2026, 9, 7))[0]
    assert event_a.event_hash() == event_b.event_hash()
    assert isinstance(event_a, Event)