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
        assert theme.current_opacity() == 0.2  # slider floor (20%) matches OPACITY_MIN
        saved = []
        settings.saved.connect(lambda v: saved.append(v))
        settings.dismiss()
        assert saved == [0.2]
        settings.close()
        calendar.close()
    finally:
        theme.set_opacity(0.75)