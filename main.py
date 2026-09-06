"""Project Scheduler — entry point.

Boot sequence (addendum sections 5 & 7):
  1. Load persistent state.
  2. Scan the vault for unchecked past tasks -> MISSED TASKS backlog.
  3. Start the polling watcher; live fire popups when the wall clock hits a
     task's minute (0–15 min grace = LATE popup).
  4. Sit quietly in the system tray (SCHEDULER / Missed Tasks / Quit).
     `--planner` opens the SCHEDULER panel on launch.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from scheduler import config, __version__
from scheduler.init_check import aggregate_missed
from scheduler.markdown_parser import complete_task, snooze_task
from scheduler.state import StateStore
from scheduler.ui.backlog import BacklogWindow
from scheduler.ui.calendar_window import CalendarWindow
from scheduler.ui.planner import GatePlanner
from scheduler.ui.popup import SystemPopup
from scheduler.ui.tray import SchedulerTray
from scheduler.watcher import TaskWatcher

log = logging.getLogger("scheduler")


def play_cue() -> None:
    """Best-effort startup WAV; never allowed to crash the app."""
    if sys.platform != "win32" or not config.CUE_WAV.exists():
        return
    try:
        import winsound

        winsound.PlaySound(str(config.CUE_WAV), winsound.SND_FILENAME | winsound.SND_ASYNC)
    except (OSError, RuntimeError):
        log.debug("Audio cue failed to play (silent mode).")


def _ensure_vault(vault: Path) -> None:
    vault.mkdir(parents=True, exist_ok=True)


def run(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    args = _parse_args(argv)
    app = QApplication(sys.argv[:1] if argv is not None else sys.argv)
    app.setQuitOnLastWindowClosed(False)

    vault = config.VAULT_DIR
    _ensure_vault(vault)
    state = StateStore(config.STATE_FILE)

    popups: set[SystemPopup] = set()

    # -- watch actions ------------------------------------------------------ #
    def on_popup_completed(task) -> None:
        complete_task(vault, task)

    def on_popup_snoozed(task, minutes: int) -> None:
        snooze_task(vault, task, minutes)

    def on_fire(payload) -> None:
        task = payload["task"]
        key = task.task_hash()
        if state.has_fired(key):
            return
        state.mark_fired(key)
        popup = SystemPopup(task, late=payload["late"], force_focus=state.force_focus)
        popup.completed.connect(on_popup_completed)
        popup.dismissed.connect(on_popup_completed)   # dismiss settles the task
        popup.snoozed.connect(on_popup_snoozed)
        popups.add(popup)
        popup.destroyed.connect(lambda _obj, p=popup: popups.discard(p))
        if state.sound:
            play_cue()
        popup.show_centered()

    watcher = TaskWatcher(vault)
    watcher.fire.connect(on_fire)

    # -- planner (persistent single instance) ------------------------------- #
    planner = GatePlanner(vault)
    planner.tasks_changed.connect(lambda: watcher.wake())  # refresh next poll soon

    def open_planner() -> None:
        planner.show_centered()

    # -- event calendar (on-demand month view) ----------------------------- #
    calendar = CalendarWindow(vault)
    planner.tasks_changed.connect(calendar.refresh)

    def open_calendar() -> None:
        calendar.refresh()
        calendar.show_centered()

    def day_to_planner(day) -> None:
        planner.select_day(day)
        planner.show_centered()

    calendar.dayActivated.connect(day_to_planner)

    # -- backlog review ------------------------------------------------------ #
    def open_backlog(initial: bool = False) -> None:
        missed = aggregate_missed(vault)
        if not missed:
            return
        backlog = BacklogWindow(missed, penalty_count=state.penalty_count, initial=initial)
        if initial:
            backlog.accepted.connect(lambda count, s=state: s.add_penalties(count) if count else None)
        backlog.reset.connect(state.reset_penalties)
        backlog.show()

    def on_quit() -> None:
        watcher.stop()
        watcher.wait(3000)
        app.quit()

    # -- tray + boot ---------------------------------------------------------- #
    tray = SchedulerTray(open_planner, open_calendar, lambda: open_backlog(initial=False), on_quit)
    open_backlog(initial=True)
    watcher.start()

    if args.planner:
        open_planner()

    log.info("Scheduler v%s online — monitoring %s (poll %ds, grace %dmin)",
             __version__, vault, config.POLL_INTERVAL_SECONDS, config.GRACE_MINUTES)
    print(f"[Scheduler {__version__}] online. Vault: {vault}")
    return app.exec()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="scheduler", description="Monochrome markdown task monitor")
    parser.add_argument("--planner", action="store_true", help="Open the SCHEDULER panel window on launch")
    args, _unknown = parser.parse_known_args(argv[1:] if argv is not None else None)
    return args


if __name__ == "__main__":
    sys.exit(run())