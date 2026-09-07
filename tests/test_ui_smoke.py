"""Headless smoke tests for the Qt layer (runs offscreen, never execs the loop)."""
from datetime import date, time, datetime

import pytest

from scheduler.models import Task, MissedTask
from scheduler.watcher import find_due_tasks


def _task(desc="Bench the build", hh="14", mm="00", done=False, day=date(2026, 9, 6)):
    return Task(
        date=day,
        time=time(int(hh), int(mm)),
        description=desc,
        done=done,
        source_file=None,
        source_line=f"- [ ] {hh}:{mm} | {desc}",
        line_no=1,
    )


def test_find_due_tasks_pure():
    now = datetime(2026, 9, 6, 14, 0, 30)
    tasks = [
        _task("Past beyond grace", hh="13"),  # 60 min past -> not live
        _task("Late within grace", hh="13", mm="59"),
        _task("Due now", hh="14", mm="00"),
        _task("Future", hh="15"),
        _task("Done past", hh="08", done=True),
    ]
    due = find_due_tasks(tasks, now, grace_minutes=15)
    descs = sorted(t.description for t in due)
    assert descs == ["Due now", "Late within grace"]


_QT_APP = None  # module-scoped strong ref: keeps the QApplication alive


def _app():
    global _QT_APP
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _QT_APP = app
    return app


def test_popup_builds_and_emits_complete():
    app = _app()
    from scheduler.ui.popup import SystemPopup

    task = _task()
    popup = SystemPopup(task, late=False)
    popup.show_centered()

    captured = []
    popup.completed.connect(captured.append)
    popup._complete()
    assert captured == [task]


def test_popup_late_badge_and_dismiss():
    app = _app()
    from scheduler.ui.popup import SystemPopup

    task = _task()
    popup = SystemPopup(task, late=True)
    popup.show_centered()
    captured = []
    popup.dismissed.connect(captured.append)
    popup.dismiss()
    assert captured == [task]


def test_popup_snooze_emits_minutes():
    app = _app()
    from scheduler.ui.popup import SystemPopup

    task = _task()
    popup = SystemPopup(task, late=True)
    popup.show_centered()
    captured = []
    popup.snoozed.connect(lambda t, m: captured.append((t, m)))
    popup._snooze(15)
    assert captured == [(task, 15)]


def test_popups_paint_without_crashing():
    """Regression: the popup card's paintEvent must not raise (missing symbol
    would escape the Qt paint virtual and fast-fail the whole app, 0xc0000409).

    `grab()` forces an offscreen render, so a missing paint symbol is caught
    here instead of taking down the process on first live show.
    """
    app = _app()
    from datetime import datetime

    from PyQt6.QtGui import QPixmap

    from scheduler.models import Event
    from scheduler.ui.popup import SystemPopup, EventReminderPopup

    task = _task()
    popup = SystemPopup(task, late=True)
    popup.show()
    frame = popup.card.grab()
    assert isinstance(frame, QPixmap)
    assert not frame.isNull()
    popup.close()

    event = Event(
        start=datetime(2026, 9, 10, 9, 0),
        end=datetime(2026, 9, 12, 18, 0),
        title="Exams",
        remind_min=None,
        done=False,
        source_file=None,
        source_line="",
        line_no=0,
    )
    reminder = EventReminderPopup(event)
    reminder.show()
    frame = reminder.card.grab()
    assert isinstance(frame, QPixmap)
    assert not frame.isNull()
    reminder.close()
    app.processEvents()


def test_backlog_builds_and_accepts():
    app = _app()
    from scheduler.ui.backlog import BacklogWindow

    missed = [MissedTask(task=_task("Dead end"), seconds_late=3600 + 900)]
    backlog = BacklogWindow(missed, penalty_count=3, initial=True)
    backlog.show()
    captured = []
    backlog.accepted.connect(captured.append)
    backlog._accept()
    assert captured == [1]
    assert backlog._list.count() == 1


def test_backlog_reset_hold_fires_on_timeout():
    app = _app()
    from scheduler.ui.backlog import BacklogWindow

    backlog = BacklogWindow([], penalty_count=7, initial=False)
    backlog.show()
    reset_fired = []
    backlog.reset.connect(lambda: reset_fired.append(True))
    backlog._arm_reset()
    backlog._reset_timer.timeout.emit()  # simulate the hold completing
    assert reset_fired == [True]
    assert backlog._reset_btn.text().startswith("RESET")


def test_calendar_window_builds_and_emits_day(tmp_path):
    app = _app()
    from PyQt6.QtWidgets import QPushButton

    from scheduler.ui.calendar_window import CalendarWindow

    calendar = CalendarWindow(tmp_path)
    calendar.show()
    captured = []
    calendar.dayActivated.connect(captured.append)
    day_cells = [b for b in calendar.findChildren(QPushButton) if "\n" in b.text()]
    assert day_cells, "expected clickable day cells"
    day_cells[0].click()
    assert len(captured) == 1
    assert captured[0].day >= 1
    calendar._shift_month(1)
    calendar._jump_today()
    calendar.close()


def test_calendar_has_close_and_settings_buttons(tmp_path):
    app = _app()
    from PyQt6.QtWidgets import QPushButton

    from scheduler.ui.calendar_window import CalendarWindow

    calendar = CalendarWindow(tmp_path)
    calendar.show()
    buttons = {b.text() for b in calendar.findChildren(QPushButton)}
    assert "✕" in buttons
    assert "⚙" in buttons
    close_btn = [b for b in calendar.findChildren(QPushButton) if b.text() == "✕"][0]
    close_btn.click()
    assert not calendar.isVisible()  # hides, never destroys (reopen is instant)
    calendar.close()


def test_settings_window_slider_drives_app_opacity():
    app = _app()
    from scheduler import config as cfg
    from scheduler.ui import theme
    from scheduler.ui.calendar_window import CalendarWindow
    from scheduler.ui.settings_window import SettingsWindow

    try:
        theme.set_opacity(0.75)
        calendar = CalendarWindow(".")
        calendar.show()
        settings = SettingsWindow()
        settings.show()
        settings._slider.setValue(90)
        assert theme.current_opacity() == 0.9
        assert cfg.WINDOW_OPACITY == 0.9
        assert abs(calendar.windowOpacity() - 0.9) < 0.02  # live update (quantized by the compositor)
        settings._slider.setValue(100)
        assert theme.current_opacity() == 1.0
        settings._slider.setValue(0)
        assert theme.current_opacity() == 0.1  # slider floor (10%) matches OPACITY_MIN
        saved = []
        settings.saved.connect(lambda v: saved.append(v))
        settings.dismiss()
        assert saved == [0.1]
        calendar.close()
    finally:
        theme.set_opacity(0.75)


def test_settings_reopen_after_dismiss_does_not_crash(tmp_path):
    """Regression: dismissing settings destroyed it, leaving a dead C++ object behind."""
    app = _app()
    from scheduler.ui import theme
    from scheduler.ui.calendar_window import CalendarWindow

    try:
        theme.set_opacity(0.75)
        calendar = CalendarWindow(tmp_path)
        calendar.show()
        for _ in range(2):
            calendar._open_settings()
            assert calendar._settings is not None
            assert calendar._settings.isVisible()
            calendar._settings.dismiss()
            app.processEvents()  # let Qt process any pending deletion events
            assert not calendar._settings.isVisible()
        assert theme.current_opacity() == 0.75
        calendar.close()
    finally:
        theme.set_opacity(0.75)


def test_settings_slider_writes_through_to_persistence_sink():
    app = _app()
    from scheduler.ui import theme
    from scheduler.ui.calendar_window import CalendarWindow

    try:
        theme.set_opacity(0.75)
        calendar = CalendarWindow(".")
        persisted = []
        calendar.set_opacity_sink(lambda v: persisted.append(v))
        calendar._open_settings()
        # change the slider after construction: fires `changed`, not just `saved`
        calendar._settings._slider.setValue(80)
        calendar._settings._slider.setValue(90)
        assert persisted[-1] == 0.9
        assert persisted == [0.8, 0.9]
        calendar.close()
    finally:
        theme.set_opacity(0.75)


def test_glow_lives_on_card_not_top_level_window(tmp_path):
    """Regression: the drop shadow must never sit on the layered top-level.

    On Windows that combination pads the window's layered update rectangle into
    negative coordinates, which Windows rejects and leaves white unpainted
    regions (the calendar white blob + UpdateLayeredWindowIndirect spam).
    """
    app = _app()
    from datetime import datetime

    from PyQt6.QtWidgets import QGraphicsDropShadowEffect

    from scheduler.models import Event
    from scheduler.ui.backlog import BacklogWindow
    from scheduler.ui.calendar_window import CalendarWindow
    from scheduler.ui.planner import GatePlanner
    from scheduler.ui.popup import EventReminderPopup, SystemPopup
    from scheduler.ui.settings_window import SettingsWindow

    event = Event(
        start=datetime(2026, 9, 10, 9, 0),
        end=datetime(2026, 9, 12, 18, 0),
        title="Exams",
        remind_min=None,
        done=False,
        source_file=None,
        source_line="",
        line_no=0,
    )
    windows = [
        CalendarWindow(tmp_path),
        GatePlanner(tmp_path),
        SettingsWindow(),
        BacklogWindow([]),
        SystemPopup(_task()),
        EventReminderPopup(event),
    ]
    for window in windows:
        assert window.window() is window, f"{type(window).__name__} should be the top level"
        assert window.graphicsEffect() is None, f"{type(window).__name__} must not glow on the top level"
        assert isinstance(window.card.graphicsEffect(), QGraphicsDropShadowEffect), type(window).__name__
        assert window.card.parentWidget() is window
    for window in windows:
        window.close()
    app.processEvents()