"""Headless smoke tests for the Qt layer (runs offscreen, never execs the loop)."""
from datetime import date, time, datetime

import pytest

from scheduler.models import Task, MissedQuest
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


def _app():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
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

    missed = [MissedQuest(task=_task("Dead end"), seconds_late=3600 + 900)]
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