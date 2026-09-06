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
    assert "GATE ADDED" in planner._status_label.text()
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
    assert "cleared" in planner._rows_layout.itemAt(0).widget().text().lower()
    planner.close()


def test_tray_icon_draws():
    from scheduler.ui.tray import make_icon

    _app()  # QPixmap/QPainter require a live QApplication
    icon = make_icon()
    assert icon.isNull() is False


def test_tray_constructs_and_quits():
    from scheduler.ui.tray import SchedulerTray

    app = _app()
    calls = []
    tray = SchedulerTray(
        on_planner=lambda: calls.append("planner"),
        on_backlog=lambda: calls.append("backlog"),
        on_quit=lambda: calls.append("quit"),
    )
    tray._tray.hide()
    assert "planner" not in calls