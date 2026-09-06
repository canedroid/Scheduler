"""Tests for event advance-notice reminders (watcher + popup)."""
from datetime import datetime

from scheduler.models import Event
from scheduler.watcher import find_event_reminders


def _event(start, end, title="Exams", remind_min=None, done=False):
    return Event(
        start=start,
        end=end,
        title=title,
        remind_min=remind_min,
        done=done,
        source_file=None,
        source_line="",
        line_no=0,
    )


def test_default_lead_day_before_fires_inside_window():
    start = datetime(2026, 9, 9, 9, 0)
    event = _event(start, datetime(2026, 9, 11, 18, 0))
    hits = find_event_reminders([event], now=datetime(2026, 9, 8, 12, 0))
    assert [(e.title, lead) for e, lead in hits] == [("Exams", 1440)]


def test_remind_token_overrides_default():
    event = _event(datetime(2026, 9, 9, 9, 0), datetime(2026, 9, 9, 17, 0), remind_min=10)
    hits = find_event_reminders([event], now=datetime(2026, 9, 9, 8, 55))
    assert len(hits) == 1 and hits[0][1] == 10


def test_no_fire_before_or_at_start():
    event = _event(datetime(2026, 9, 9, 9, 0), datetime(2026, 9, 9, 17, 0), remind_min=10)
    assert find_event_reminders([event], now=datetime(2026, 9, 9, 9, 0)) == []
    assert find_event_reminders([event], now=datetime(2026, 9, 9, 10, 0)) == []
    assert find_event_reminders([event], now=datetime(2026, 9, 9, 8, 49)) == []


def test_done_events_never_remind():
    start = datetime(2026, 9, 9, 9, 0)
    event = _event(start, datetime(2026, 9, 9, 17, 0), done=True)
    assert find_event_reminders([event], now=datetime(2026, 9, 8, 12, 0)) == []


def test_zero_or_none_lead_never_fires():
    start = datetime(2026, 9, 9, 9, 0)
    event = _event(start, datetime(2026, 9, 9, 17, 0), remind_min=0)
    assert find_event_reminders([event], now=datetime(2026, 9, 9, 8, 30)) == []


def test_watcher_polls_event_horizon(tmp_path):
    from datetime import date, datetime

    from scheduler.markdown_parser import read_events_range

    start_file = tmp_path / "2026-09-11.md"
    start_file.write_text("- [ ] 2026-09-12 09:00 → 2026-09-12 18:00 | Demo (⏰ 1h)\n", encoding="utf-8")
    events = read_events_range(tmp_path, date(2026, 9, 11), date(2026, 9, 12))
    hits = find_event_reminders(events, now=datetime(2026, 9, 12, 8, 30))
    assert [(e.title, lead) for e, lead in hits] == [("Demo", 60)]
    assert read_events_range(tmp_path, date(2026, 9, 12), date(2026, 9, 12)) == []  # stored in start-day file


def test_popup_eta_text():
    from scheduler.ui.popup import event_eta_text

    assert event_eta_text(datetime(2026, 9, 10, 9, 0), now=datetime(2026, 9, 9, 12, 0)) == "Starting tomorrow at 09:00"
    assert event_eta_text(datetime(2026, 9, 9, 9, 0), now=datetime(2026, 9, 9, 8, 0)) == "Starting today at 09:00"


def test_popup_builds_and_signals():
    from PyQt6.QtWidgets import QApplication, QLabel  # noqa: F401

    app = QApplication.instance() or QApplication([])
    from scheduler.ui.popup import EventReminderPopup

    event = _event(datetime(2026, 9, 10, 9, 0), datetime(2026, 9, 12, 18, 0))
    popup = EventReminderPopup(event, now=datetime(2026, 9, 9, 12, 0))
    popup.show()
    labels = [w.text() for w in popup.findChildren(QLabel)]
    assert any("Starting tomorrow at 09:00" in text for text in labels)
    fired = []
    popup.openPlanner.connect(lambda: fired.append("planner"))
    popup.dismissed.connect(lambda: fired.append("dismiss"))
    popup._open_planner()
    assert fired == ["planner"]
    popup.close()
    app.processEvents()