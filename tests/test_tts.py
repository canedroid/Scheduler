"""Tests for the spoken fire announcement (pure builder + guarded speak)."""
from datetime import date, time

import pytest

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