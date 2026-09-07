from datetime import date, time

from PyQt6.QtCore import QDate, QTime
from PyQt6.QtWidgets import QApplication

_QT_APP = None  # module-scoped strong ref: keeps the QApplication alive


def _app():
    global _QT_APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _QT_APP = app
    return app


def _write(vault, name, content):
    path = vault / name
    path.write_text(content, encoding="utf-8")
    return path


def test_planner_add_gate_writes_file(today_vault):
    from scheduler.ui.planner import GatePlanner

    app = _app()
    planner = GatePlanner(today_vault)
    planner.show_centered()
    planner._date_edit.setDate(QDate(2026, 10, 5))
    planner._time_edit.setTime(QTime(23, 59))
    planner._desc_edit.setText("Launch sequence")
    planner._add_task()

    content = (today_vault / "2026-10-05.md").read_text(encoding="utf-8")
    assert content.startswith("# 2026-10-05\n")
    assert "- [ ] 23:59 | Launch sequence\n" in content
    assert planner._status_label.isVisible()
    assert "TASK ADDED" in planner._status_label.text()
    planner.close()


def test_planner_rejects_blank_description(today_vault):
    from scheduler.ui.planner import GatePlanner

    app = _app()
    planner = GatePlanner(today_vault)
    planner.show_centered()
    planner._desc_edit.setText("   ")
    planner._add_task()
    assert planner._status_label.isVisible()
    assert "description" in planner._status_label.text().lower()
    planner.close()


def test_planner_completes_existing_task(today_vault):
    from scheduler.markdown_parser import read_tasks
    from scheduler.ui.planner import GatePlanner

    app = _app()
    _write(today_vault, "2026-09-06.md", "- [ ] 08:00 | Morning miss\n")
    planner = GatePlanner(today_vault)
    planner._date_edit.setDate(QDate(2026, 9, 6))
    # re-extract via the public parser to confirm independent behavior:
    (task,) = read_tasks(today_vault, date(2026, 9, 6))
    planner._task_done(task)
    assert "- [x] 08:00 | Morning miss\n" in (today_vault / "2026-09-06.md").read_text(encoding="utf-8")
    planner.close()


def test_planner_delete_existing_task(today_vault):
    from scheduler.markdown_parser import read_tasks
    from scheduler.ui.planner import GatePlanner

    app = _app()
    _write(today_vault, "2026-09-06.md", "- [ ] 08:00 | Remove me\n- [ ] 09:00 | Keep me\n")
    planner = GatePlanner(today_vault)
    tasks = read_tasks(today_vault, date(2026, 9, 6))
    victim = next(t for t in tasks if t.description == "Remove me")
    planner._task_delete(victim)
    content = (today_vault / "2026-09-06.md").read_text(encoding="utf-8")
    assert "Remove me" not in content
    assert "- [ ] 09:00 | Keep me\n" in content
    planner.close()


def test_planner_edit_time_then_delete_row(today_vault):
    from PyQt6.QtWidgets import QPushButton, QTimeEdit

    from scheduler.ui.planner import GatePlanner

    app = _app()
    _write(today_vault, "2026-09-06.md", "- [ ] 08:00 | Move & remove\n- [ ] 09:00 | Keep me\n")
    planner = GatePlanner(today_vault)
    planner.show_centered()
    planner._date_edit.setDate(QDate(2026, 9, 6))
    # find the row for the 08:00 task
    te = [w for w in planner.findChildren(QTimeEdit) if w.time().toString("HH:mm") == "08:00"][0]
    row = te.parentWidget()
    x_btn = [w for w in row.findChildren(QPushButton) if w.toolTip() == "Delete task"][0]
    # user edits the time (reschedule pending), then clicks X before leaving the row
    te.setTime(QTime(20, 0))
    te.editingFinished.emit()  # fires the row's lambda with ITS OWN task object
    x_btn.click()
    planner.card._refresh_timer.stop()  # cancel any deferred rebuild noise
    content = (today_vault / "2026-09-06.md").read_text(encoding="utf-8")
    assert "Move & remove" not in content
    assert "- [ ] 09:00 | Keep me\n" in content
    planner.close()


def test_planner_x_after_focus_change_not_clobbered(today_vault):
    """The row must survive an editingFinished-triggered refresh, so a real
    mouse click on ✕ still lands after the user edited that row's time."""
    from PyQt6.QtWidgets import QPushButton, QTimeEdit

    from scheduler.ui.planner import GatePlanner

    app = _app()
    _write(today_vault, "2026-09-06.md", "- [ ] 08:00 | Focus change\n- [ ] 09:00 | Keep me\n")
    planner = GatePlanner(today_vault)
    planner.show_centered()
    planner._date_edit.setDate(QDate(2026, 9, 6))
    te = [w for w in planner.findChildren(QTimeEdit) if w.time().toString("HH:mm") == "08:00"][0]
    te.setFocus()
    te.setTime(QTime(20, 0))
    # moving focus fires editingFinished -> _apply_reschedule -> (deferred) refresh
    te.clearFocus()
    planner.card._refresh_timer.stop()  # editingFinished path schedules, not rebuilds
    row = te.parentWidget()
    x_btn = [w for w in row.findChildren(QPushButton) if w.toolTip() == "Delete task"][0]
    x_btn.click()
    planner.card._refresh_timer.stop()
    content = (today_vault / "2026-09-06.md").read_text(encoding="utf-8")
    assert "Focus change" not in content
    planner.close()


def test_planner_hides_done_tasks(today_vault):
    from scheduler.ui.planner import GatePlanner

    app = _app()
    _write(
        today_vault,
        "2026-09-06.md",
        "- [ ] 08:00 | Still pending\n- [x] 09:00 | Already done\n- [X] 10:00 | Also done\n",
    )
    planner = GatePlanner(today_vault)
    planner._date_edit.setDate(QDate(2026, 9, 6))
    descs = [t.description for t in planner._tasks]
    assert descs == ["Still pending"]


def test_planner_cleared_message_when_all_done(today_vault):
    from scheduler.ui.planner import GatePlanner

    app = _app()
    _write(today_vault, "2026-09-06.md", "- [x] 08:00 | Done one\n- [x] 09:00 | Done two\n")
    planner = GatePlanner(today_vault)
    planner._date_edit.setDate(QDate(2026, 9, 6))
    assert planner._tasks == []
    assert planner._section_label.text().endswith("(0)")
    assert "completed" in planner._rows_layout.itemAt(0).widget().text().lower()
    planner.close()


def test_tray_icon_draws():
    from scheduler.ui.tray import make_icon

    _app()  # QPixmap/QPainter require a live QApplication
    icon = make_icon()
    assert icon.isNull() is False


def test_planner_add_event_writes_range_line(today_vault):
    from scheduler.ui.planner import GatePlanner

    app = _app()
    planner = GatePlanner(today_vault)
    planner._ev_start_date.setDate(QDate(2026, 10, 5))
    planner._ev_end_date.setDate(QDate(2026, 10, 6))
    planner._ev_end_time.setTime(QTime(9, 0))
    planner._ev_title.setText("Concert")
    planner._add_event()
    content = (today_vault / "2026-10-05.md").read_text(encoding="utf-8")
    assert "- [ ] 2026-10-05 09:00 → 2026-10-06 09:00 | Concert\n" in content
    assert "EVENT ADDED" in planner._status_label.text()
    assert planner._rows_layout.count() > 0
    planner.close()


def test_planner_event_with_remind_token_round_trips(today_vault):
    from scheduler.ui.planner import GatePlanner

    app = _app()
    planner = GatePlanner(today_vault)
    planner._ev_start_date.setDate(QDate(2026, 10, 8))
    planner._ev_start_time.setTime(QTime(14, 0))
    planner._ev_end_date.setDate(QDate(2026, 10, 8))
    planner._ev_end_time.setTime(QTime(16, 0))
    planner._ev_remind.setCurrentIndex(1)  # 10 min before
    planner._ev_title.setText("Quick pickup")
    planner._add_event()
    content = (today_vault / "2026-10-08.md").read_text(encoding="utf-8")
    assert "- [ ] 2026-10-08 14:00 → 2026-10-08 16:00 | Quick pickup (⏰ 10m)\n" in content
    planner.close()


def test_planner_rejects_bad_event_range(today_vault):
    from scheduler.ui.planner import GatePlanner

    app = _app()
    planner = GatePlanner(today_vault)
    planner._ev_start_date.setDate(QDate(2026, 10, 10))
    planner._ev_end_date.setDate(QDate(2026, 10, 9))
    planner._ev_title.setText("Time travel")
    planner._add_event()
    assert "end must be after start" in planner._status_label.text().lower()
    planner.close()


def test_tray_constructs_and_quits():
    from scheduler.ui.tray import SchedulerTray

    app = _app()
    calls = []
    tray = SchedulerTray(
        on_planner=lambda: calls.append("planner"),
        on_calendar=lambda: calls.append("calendar"),
        on_backlog=lambda: calls.append("backlog"),
        on_quit=lambda: calls.append("quit"),
    )
    tray._tray.hide()
    assert "planner" not in calls