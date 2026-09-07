from datetime import date, time

import pytest

from scheduler.markdown_parser import (
    add_task,
    complete_task,
    delete_task,
    parse_tasks_from_file,
    read_all_tasks,
    read_tasks,
    reschedule_task,
    snooze_task,
)
from scheduler.models import Task


def _write(vault, name, content):
    path = vault / name
    path.write_text(content, encoding="utf-8")
    return path


SAMPLE = """# 2026-09-06

- [ ] 14:00 | Task description
- [x] 09:00 | Already done
- [X] 10:15 Done uppercase pipe-less
- [ ] 08:30 No pipe marker here
- [ ] 12:00 | Single-digit hour variant
- [ ] 16:45:30 | With seconds (tolerated input)

not a task line
- [ ] 99:99 | Invalid time, ignored
- [ ] 10:00 | 
empty descriptions are skipped
"""


@pytest.fixture
def vault(tmp_path):
    return tmp_path


def test_parse_roundtrip(vault):
    _write(vault, "2026-09-06.md", SAMPLE)
    tasks = read_tasks(vault, date(2026, 9, 6))
    assert [t.description for t in tasks] == [
        "Task description",
        "Already done",
        "Done uppercase pipe-less",
        "No pipe marker here",
        "Single-digit hour variant",
        "With seconds (tolerated input)",
    ]
    assert tasks[0].time == time(14, 0)
    assert tasks[0].done is False
    assert tasks[1].done is True
    assert tasks[2].done is True  # uppercase X accepted
    assert tasks[4].time == time(12, 0)  # 12:00, not "12:00 | "
    assert tasks[5].time == time(16, 45, 30)  # seconds preserved on read
    assert tasks[5].description == "With seconds (tolerated input)"


def test_read_tasks_missing_file(vault):
    assert read_tasks(vault, date(2020, 1, 1)) == []


def test_read_all_tasks_recurses_and_filters_names(vault):
    _write(vault, "2026-09-06.md", SAMPLE)
    _write(vault, "2026-09-07.md", "- [ ] 07:00 | Tomorrow task\n")
    (vault / "sub").mkdir()
    _write(vault, "sub/2026-09-05.md", "- [ ] 06:00 | Nested missed task\n")
    _write(vault, "sub/scratch-notes.md", "- [ ] 06:00 | Ignored, not date-named\n")

    tasks = read_all_tasks(vault)
    descs = sorted(t.description for t in tasks)
    assert descs == [
        "Already done",
        "Done uppercase pipe-less",
        "Nested missed task",
        "No pipe marker here",
        "Single-digit hour variant",
        "Task description",
        "Tomorrow task",
        "With seconds (tolerated input)",
    ]
    nested = next(t for t in tasks if t.source_file.parent.name == "sub")
    assert nested.date == date(2026, 9, 5)


def test_complete_task_line_anchor(vault):
    path = _write(vault, "2026-09-06.md", SAMPLE)
    tasks = read_tasks(vault, date(2026, 9, 6))
    target = next(t for t in tasks if t.description == "Task description")

    assert complete_task(vault, target) is True
    content = path.read_text(encoding="utf-8")
    assert "- [x] 14:00 | Task description" in content
    assert "- [x] 09:00 | Already done" in content  # untouched neighbor
    assert target.done is True


def test_complete_already_done_noop(vault):
    _write(vault, "2026-09-06.md", "- [x] 09:00 | Done\n")
    (task,) = read_tasks(vault, date(2026, 9, 6))
    assert complete_task(vault, task) is False


def test_complete_aborts_when_user_edited_line(vault):
    path = _write(vault, "2026-09-06.md", "- [ ] 14:00 | Original\n")
    (task,) = read_tasks(vault, date(2026, 9, 6))
    # User rewrites the line before we write back -> anchor no longer matches.
    path.write_text("- [ ] 14:00 | User changed me\n", encoding="utf-8")
    assert complete_task(vault, task) is False
    assert "- [ ] 14:00 | User changed me" in path.read_text(encoding="utf-8")
    assert "Original" not in path.read_text(encoding="utf-8")


def test_complete_handles_no_trailing_newline(vault):
    path = _write(vault, "2026-09-06.md", "- [ ] 14:00 | Bare")
    (task,) = read_tasks(vault, date(2026, 9, 6))
    assert complete_task(vault, task) is True
    assert path.read_text(encoding="utf-8") == "- [x] 14:00 | Bare\n"


def test_snooze_rewrites_time_and_normalizes(vault):
    path = _write(vault, "2026-09-06.md", "- [ ] 9:05 | Early train\n- [ ] 11:00 | Untouched\n")
    tasks = read_tasks(vault, date(2026, 9, 6))
    early = next(t for t in tasks if t.description == "Early train")

    assert snooze_task(vault, early, 15) is True
    content = path.read_text(encoding="utf-8")
    assert "- [ ] 09:20 | Early train\n" in content  # normalized to HH:MM
    assert "- [ ] 11:00 | Untouched\n" in content
    assert early.time == time(9, 20)
    assert early.source_line == "- [ ] 09:20 | Early train"


def test_snooze_keeps_deletable_anchor(vault):
    path = _write(vault, "2026-09-06.md", "- [ ] 9:05 | Early train\n")
    tasks = read_tasks(vault, date(2026, 9, 6))
    early = tasks[0]
    assert snooze_task(vault, early, 15) is True
    assert delete_task(vault, early) is True
    assert "Early train" not in path.read_text(encoding="utf-8")


def test_snooze_with_pipe_preserves_description(vault):
    path = _write(vault, "2026-09-06.md", "- [ ] 23:50 | Late night grind\n")
    (task,) = read_tasks(vault, date(2026, 9, 6))
    assert snooze_task(vault, task, 30) is True
    content = path.read_text(encoding="utf-8")
    assert "- [ ] 00:20 | Late night grind\n" in content  # rolls past midnight


def test_task_hash_stable():
    task = Task(
        date=date(2026, 9, 6),
        time=time(14, 0),
        description="Task description",
        done=False,
        source_file=None,
        source_line="- [ ] 14:00 | Task description",
        line_no=2,
    )
    assert task.task_hash() == task.task_hash()
    other = Task(date(2026, 9, 6), time(14, 0), "Task description", False, None, "", 0)
    assert task.task_hash() == other.task_hash()


def test_add_task_creates_new_file(vault):
    assert add_task(vault, date(2026, 10, 1), time(9, 0), "First gate")
    path = vault / "2026-10-01.md"
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert content.startswith("# 2026-10-01\n")
    assert "- [ ] 09:00 | First gate\n" in content


def test_add_task_appends_to_existing(vault):
    _write(vault, "2026-09-06.md", SAMPLE)
    assert add_task(vault, date(2026, 9, 6), time(21, 5), "Night gate")
    content = (vault / "2026-09-06.md").read_text(encoding="utf-8")
    assert content.rstrip("\n").endswith("- [ ] 21:05 | Night gate")
    assert "- [ ] 14:00 | Task description" in content  # untouched


def test_add_task_rejects_invalid(vault):
    assert add_task(vault, date(2026, 9, 6), time(9, 0), "   ") is False
    assert not (vault / "2026-09-06.md").exists()


def test_delete_task_removes_exact_line(vault):
    path = _write(vault, "2026-09-06.md", "- [ ] 14:00 | Task description\n- [x] 09:00 | Already done\n")
    tasks = read_tasks(vault, date(2026, 9, 6))
    victim = next(t for t in tasks if t.description == "Task description")
    assert delete_task(vault, victim) is True
    content = path.read_text(encoding="utf-8")
    assert "Task description" not in content
    assert "- [x] 09:00 | Already done\n" in content


def test_delete_aborts_on_user_edit(vault):
    path = _write(vault, "2026-09-06.md", "- [ ] 14:00 | Original\n")
    (task,) = read_tasks(vault, date(2026, 9, 6))
    path.write_text("- [ ] 14:00 | User edited it\n", encoding="utf-8")
    assert delete_task(vault, task) is False
    assert "- [ ] 14:00 | User edited it\n" in path.read_text(encoding="utf-8")


def test_reschedule_task_explicit_time(vault):
    path = _write(vault, "2026-09-06.md", "- [ ] 14:00 | Task description\n- [ ] 10:00 | Neighbor\n")
    tasks = read_tasks(vault, date(2026, 9, 6))
    target = next(t for t in tasks if t.description == "Task description")
    assert reschedule_task(vault, target, time(18, 30)) is True
    content = path.read_text(encoding="utf-8")
    assert "- [ ] 18:30 | Task description\n" in content
    assert "- [ ] 10:00 | Neighbor\n" in content
    assert target.time == time(18, 30)
    assert target.source_line == "- [ ] 18:30 | Task description"


def test_reschedule_then_delete_uses_fresh_anchor(vault):
    path = _write(vault, "2026-09-06.md", "- [ ] 14:00 | Task description\n- [ ] 10:00 | Neighbor\n")
    tasks = read_tasks(vault, date(2026, 9, 6))
    target = next(t for t in tasks if t.description == "Task description")
    assert reschedule_task(vault, target, time(18, 30)) is True
    assert delete_task(vault, target) is True  # must match the rewritten line
    content = path.read_text(encoding="utf-8")
    assert "Task description" not in content
    assert "- [ ] 10:00 | Neighbor\n" in content