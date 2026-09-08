"""Tests for the spoken fire announcement (pure builder + guarded speak)."""
from datetime import date, datetime, time

import pytest

from main import announce_live_fire
from scheduler.models import Task
from scheduler.tts import _dispatch, speak, task_announcement


def _task(desc="Water the plants", late=False):
    return Task(
        date=date(2026, 9, 7),
        time=time(17, 56),
        description=desc,
        done=False,
        source_file=None,
        source_line=f"- [ ] 17:56 | {desc}",
        line_no=1,
    )


def test_announcement_due_task():
    assert task_announcement(_task()) == "Time for Water the plants"


def test_announcement_late_task():
    assert task_announcement(_task(), late=True) == "Late for Water the plants"


def test_announcement_fallback_when_description_blank():
    assert task_announcement(_task("   ")) == "Time for your scheduled task"
    assert task_announcement(_task(""), late=True) == "Late for your scheduled task"


def test_speak_returns_without_error():
    seen = {}
    import threading

    original = threading.Thread

    class FakeThread(original):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            seen["spawned"] = True

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(threading, "Thread", FakeThread)
        speak("hello")
    assert seen.get("spawned") is True


def test_dispatch_swallows_voice_errors(monkeypatch):
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        pytest.skip("pywin32 not installed")

    def boom(*_a, **_k):
        raise RuntimeError("SAPI unavailable")

    monkeypatch.setattr(win32com.client, "Dispatch", boom)
    _dispatch("hello")  # must not raise


def _boot(started_h, started_m, task_h=13, task_m=10):
    started = datetime(2026, 9, 8, started_h, started_m)
    scheduled = datetime(2026, 9, 8, task_h, task_m)
    return scheduled, started


def test_catch_up_after_launch_is_silent_when_late():
    """App opened 13:12 for a 13:10 task -> LATE fire -> no TTS/chime."""
    scheduled, started = _boot(started_h=13, started_m=12)
    assert announce_live_fire(late=True, scheduled=scheduled, app_started=started) is False


def test_catch_up_after_launch_is_silent_even_in_grace():
    """Same case but with the grace-friendly 'on time' flag still gated by boot time."""
    scheduled, started = _boot(started_h=13, started_m=12)
    assert announce_live_fire(late=False, scheduled=scheduled, app_started=started) is False


def test_task_fired_after_launch_is_loud():
    """App open since 12:50, 13:10 task fires on time -> speak/chime."""
    scheduled, started = _boot(started_h=12, started_m=50)
    assert announce_live_fire(late=False, scheduled=scheduled, app_started=started) is True


def test_same_minute_launch_is_silent():
    """App opened 13:10:30 for a 13:10 task -> scheduled before launch -> silent."""
    scheduled = datetime(2026, 9, 8, 13, 10, 0)
    started = datetime(2026, 9, 8, 13, 10, 30)
    assert announce_live_fire(late=False, scheduled=scheduled, app_started=started) is False