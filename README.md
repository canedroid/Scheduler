# Project Scheduler

A zero-cost, local, monochrome schedule monitor. Reads timestamped
tasks from plain Markdown in an **Obsidian-compatible vault**, then fires a
frameless, transparent dark-glass popup with glowing gray borders the moment a
task's minute arrives. Missed schedules are caught up at boot as a
**SCHEDULER** review backlog.

## File format

One file per calendar day, named `YYYY-MM-DD.md`. Each line is one task:

```markdown
- [ ] 14:00 | Deep focus block
- [x] 06:30 | Morning calibration
- [ ] 09:00 Written form also works (pipe optional)
```

- 24-hour `HH:MM` clock (`HH:MM:SS` tolerated on read, normalized on write).
- `- [ ]` = pending, `- [x]` (or `- [X]`) = completed.
- Subfolders are scanned, but only `<date>.md` files count as schedules.
- Point this at an existing Obsidian vault by editing `scheduler/config.py` → `VAULT_DIR`.

### Multi-day events (month calendar)

Range events live in the **start day's** file as a dated range line:

```markdown
- [ ] 2026-09-07 09:00 → 2026-09-09 18:00 | Exams (⏰ 1d)
```

- The `(⏰ …)` suffix sets an advance-notice lead (`m`/`h`/`d`); without it the lead
  defaults to **day-before**. Same-day events don't need a range — they're plain tasks.
- The tray menu's **▦ Calendar** opens a month view showing pending-task counts and
  event coverage; clicking a day jumps the scheduler panel to that day. The header's
  **✕** closes it, and **⚙** opens a transparency slider.
- **Window transparency** — the calendar's **⚙** button opens a live slider
  (20–100%) that re-tints the calendar, planner and missed-task windows on the
  spot. The choice is saved to `scheduler_state.json` and restored on launch.
- When a range event enters its advance window, a frameless `REMINDER` popup
  appears in the system tray announcing the upcoming event (the `OPEN PLANNER`
  button jumps to the event's day).

## Setup

```powershell
# Python 3.11+ (PyQt6 required)
py -3 -m pip install -r requirements.txt
```

## Run

```powershell
py -3 main.py
```

or double-click `run_scheduler.bat`. Nothing is shown until an alert fires — the
app sits quietly in the system tray (gray `◈` icon, right-click for the menu),
polling every 10 s. A sample vault ships with a demo past-due task so you see the
backlog on first boot.

### Login autostart (optional)

1. Edit `scripts/scheduler-login-task.xml` → set `<Command>` to your repo's
   `run_scheduler.bat`.
2. Register once:

   ```powershell
   schtasks /create /tn "Scheduler" /xml "%CD%\scripts\scheduler-login-task.xml"
   ```

## Adding schedules — two ways

### 1. Scheduler panel (recommended for daily use)

Right-click the tray icon → **▣ SCHEDULER** (or left-click the tray icon, or
launch with `py -3 main.py --planner`). The planner is a frameless HUD panel
matching the popup aesthetic:

- Pick a **DAY**, type a **time** + **description**, hit **ADD TASK** — it
  writes `- [ ] HH:MM | description` into the right `YYYY-MM-DD.md` (creating the
  file if needed).
- Existing tasks for that day are listed below with inline controls: edit the
  time to reschedule, **✓** to mark complete, **✕** to delete.
- Completed tasks are hidden automatically; when every task for a day is done the
  panel shows the cleared message.
- Every write is line-anchored and re-read afterwards, so edits made in Obsidian
  are never clobbered.

### 2. Edit markdown directly

```powershell
notepad D:\randombullshitgoburr\Scheduler\vault\2026-09-06.md
```

## Behavior

| Event                                             | Result                                            |
| ------------------------------------------------- | ------------------------------------------------- |
| Clock reaches `- [ ] HH:MM`                       | Floating popup (Complete / Snooze +5/+15/+30 / Dismiss) |
| Task is 0–15 min late                             | Live **LATE** popup                               |
| Task is >15 min late (app was off)                | Captured by boot-time **MISSED TASKS** backlog   |
| Popup is completed/dismissed/snoozed              | Markdown rewritten in place (line-anchored, conflict-safe) |
| Missed task accepted            | `penalty_count` +1 (persistent, manual hold-to-reset) |

The popup never steals focus (pure toast). Opt into alert behavior with
`"force_focus": true` in `scheduler_state.json`.

## Tests

```powershell
py -3 -m pytest
```

Covers parsing, line-anchored writes, grace-window classification, missed-task
aggregation, and headless UI smoke checks (offscreen).

## Performance

~41 MB RAM idle in the tray, 0% CPU. A 600-task vault polls in under 1 ms.
See **[BENCHMARKS.md](BENCHMARKS.md)** for full numbers.

## Layout

```
main.py                  entry point (+ --planner flag)
scheduler/config.py      paths, timing, theme, task-line regex
scheduler/markdown_parser.py   read / complete / snooze / reschedule / add / delete (line-anchor writes)
scheduler/init_check.py  boot-time missed-schedule scan + classification
scheduler/state.py       JSON cache (penalties, fired hashes, prefs)
scheduler/watcher.py     polling QThread -> live popup events
scheduler/ui/popup.py    frameless transparent notification
scheduler/ui/backlog.py  MISSED TASKS review window
scheduler/ui/planner.py  SCHEDULER panel (add / reschedule / complete / delete)
scheduler/ui/tray.py     system tray icon + menu
vault/                   sample markdown vault
scripts/                 login task + cue-wav generator
tests/                   pytest suite
```