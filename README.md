# Project Scheduler

A zero-cost, local, Solo Leveling themed schedule monitor. Reads timestamped
tasks from plain Markdown in an **Obsidian-compatible vault**, then fires a
frameless, transparent dark-glass popup with glowing purple borders the moment a
task's minute arrives. Missed schedules are caught up at boot as a
**PENALTY GATE** backlog.

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
app sits quietly in the background, polling every 10 s. A sample vault ships with
a demo past-due task so you see the backlog on first boot.

### Login autostart (optional)

1. Edit `scripts/scheduler-login-task.xml` → set `<Command>` to your repo's
   `run_scheduler.bat`.
2. Register once:

   ```powershell
   schtasks /create /tn "Scheduler" /xml "%CD%\scripts\scheduler-login-task.xml"
   ```

## Behavior

| Event                                             | Result                                            |
| ------------------------------------------------- | ------------------------------------------------- |
| Clock reaches `- [ ] HH:MM`                       | Floating popup (Complete / Snooze +5/+15/+30 / Dismiss) |
| Task is 0–15 min late                             | Live **LATE** popup                               |
| Task is >15 min late (app was off)                | Captured by boot-time **MISSED QUESTS** backlog   |
| Popup is completed/dismissed/snoozed              | Markdown rewritten in place (line-anchored, conflict-safe) |
| Missed quest accepted            | `penalty_count` +1 (persistent, manual hold-to-reset) |

The popup never steals focus (pure toast). Opt into alert behavior with
`"force_focus": true` in `scheduler_state.json`.

## Tests

```powershell
py -3 -m pytest
```

Covers parsing, line-anchored writes, grace-window classification, missed-task
aggregation, and headless UI smoke checks (offscreen).

## Layout

```
main.py                  entry point
scheduler/config.py      paths, timing, theme, task-line regex
scheduler/markdown_parser.py   read / complete / snooze (line-anchor writes)
scheduler/init_check.py  boot-time missed-schedule scan + classification
scheduler/state.py       JSON cache (penalties, fired hashes, prefs)
scheduler/watcher.py     polling QThread -> live popup events
scheduler/ui/popup.py    frameless transparent notification
scheduler/ui/backlog.py  MISSED QUESTS review window
vault/                   sample markdown vault
scripts/                 login task + cue-wav generator
tests/                   pytest suite
```