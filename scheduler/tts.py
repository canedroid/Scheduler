"""Windows text-to-speech for live task announcements.

Speaks the fired task's description via the system SAPI voice. Deliberately
win32-only and best-effort like `main.play_cue`: any failure is swallowed so a
missing/blocked voice can never crash the app.
"""
from __future__ import annotations

import sys
import threading

from scheduler.models import Task

SPEECH_FAIL_LOG = None  # assigned by the app once logging is configured


def task_announcement(task: Task, late: bool = False) -> str:
    """Human sentence announcing a fired task (short and SAPI-friendly)."""
    description = (task.description or "").strip()
    if not description:
        description = "your scheduled task"
    prefix = "Late for" if late else "Time for"
    return f"{prefix} {description}"


def speak(text: str) -> None:
    """Fire-and-forget announcement; never raises."""
    if sys.platform != "win32":
        return
    threading.Thread(target=_dispatch, args=(text,), daemon=True).start()


def _dispatch(text: str) -> None:
    try:
        import win32com.client  # type: ignore[import-not-found]

        voice = win32com.client.Dispatch("SAPI.SpVoice")
        voice.Speak(str(text))
    except Exception:
        if SPEECH_FAIL_LOG is not None:
            SPEECH_FAIL_LOG.debug("TTS announcement failed (silent mode).")