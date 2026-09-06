System Blueprint: Project "Scheduler"
1. Why I Want This (The Core Motivation)
Traditional productivity apps and digital calendars are uninspiring, sterile, and easily ignored. They lack psychological friction and urgency. This project is built to merge an intense, gamified monochrome aesthetic (dark glass, white accents, stark warning boxes, and system prompts) with raw, zero-cost, local productivity. By using a Markdown-based storage system (compatible with Obsidian) paired with a custom-built desktop interface, it ensures total data privacy, portability, and zero subscription costs while turning daily scheduling into an immersive system boot-up.

2. What It Will Do (Core Functionality)
Markdown Integration: Reads, parses, and writes to local Markdown files containing timestamped tasks and schedules.

The System Pop-Up: Triggers an immersive, floating, frameless dark-glass window with glowing gray borders and warning icons right when a scheduled event's timestamp is hit.

Missed Schedule Catch-Up: Automatically detects uncompleted tasks from past timestamps upon app boot-up, flagging them as a "Penalty/Missed Gate" and presenting them in a backlog review screen.

Persistent Local State: Saves check-ins, completions, and schedule adjustments locally without requiring a remote database or cloud server.

3. Where It Will Store the Data
Local Markdown Files (.md): Stored directly in a designated local directory (which can be an existing Obsidian vault). Files are structured chronologically (e.g., daily or weekly logs) using standard Markdown checkboxes and time strings (e.g., - [ ] 14:00 | Task description).

Local State Cache: A lightweight local JSON or SQLite file to track app preferences, window states, and notification flags.

4. When It Will Work
Background Monitoring: A lightweight Python background daemon/thread runs continuously while the user's computer is on, checking system time against active task timestamps.

Boot-Up Sequence: Instantly evaluates missed schedules the moment the application is launched.

Real-Time Interception: Fires alerts precisely at the designated timestamp minute.

5. The "Who" (Skipped by Design)
Intentionally omitted as a solo, local developer project.

6. How It Will Work (Architecture & Technical Workflow)
Core Engine (Python):

Uses a file watcher or periodic polling mechanism to monitor the Markdown schedule directory.

Parses time strings using Python's datetime and regular expressions (re) to map out active schedules.

UI & Styling Layer:

Built using CustomTkinter or PyQt6 for a modern, frameless, transparent, and custom-styled window that mimics the dark Sci-Fi HUD of the Solo Leveling system UI.

Notification & Alert Logic:

When Current Time == Task Timestamp, a background thread triggers the main GUI thread to render the popup notification over other windows.

If the app was closed during a timestamp, the startup initialization script scans all files for unchecked past timestamps and aggregates them into a "Missed Tasks" summary window.

---

## Addendum: Locked Design Contract (v1)

### 1. Time Format Contract
Canonical schedule syntax per task line: `- [ ] HH:MM | Task description`.
- Strict 24-hour clock. `HH:MM` only on read AND write. `HH:MM:SS` is tolerated on input
  but normalized to `HH:MM` on any rewrite.
- No AM/PM, no recurring tasks, no duration/priority fields in v1 (schema space reserved).
- Marker `|` is optional: `- [ ] 09:00 Wake up` and `- [ ] 09:00 | Wake up` both parse.

### 2. Missed-Task Lifecycle
- A task settles only by becoming `- [x]` — manually, or via popup Complete/Dismiss.
- Scans NEVER mutate markdown. The backlog merely presents missed tasks.
- Re-scheduling = user edits the time string in the `.md`; the watcher picks up the new
  time on the next poll (~10s). Missed tasks stay `- [ ]` until settled, so they re-appear
  in backlog until the user resolves them.

### 3. File Location Contract
- One file per calendar day, named `YYYY-MM-DD.md`, at the vault root. Each line = one task.
- The scanner recurses into subfolders (Obsidian may nest files) but only matches files
  conforming to the `<date>.md` naming convention. Tolerates a leading `#` title line and
  blank lines.

### 4. Snooze / Dismiss Semantics
- Popup actions: **Complete** (marks `- [x]`), **Dismiss** (auto-completes + suppresses
  refire by persisted task-hash), **Snooze +5 / +15 / +30** (rewrites the task's `HH:MM`
  forward via line-anchor write).
- Popup is non-modal float; auto-hides after 20s.

### 5. OS Autostart
- v1 ships `run_scheduler.bat` (double-click to launch background monitor) plus a
  `scripts/scheduler-login-task.xml` Task Scheduler recipe for login autostart.
  No background OS service/daemon.

### 6. Always-On-Top & Focus
- Passive-toast semantics: `WindowStaysOnTopHint`, frameless translucent, NEVER steals
  focus/activation. Click anywhere dismisses (besides buttons).
- User may opt in to `force_focus=true` in state for an alert behavior.

### 7. Clock Edge Cases
- **Grace window: 15 minutes.** If the watcher's poll finds an unchecked task whose
  minute is 0–15 min past, it fires a live popup marked **LATE**.
- If the minute is >15 min past (app was off/asleep), it skips the live popup and the
  task is captured by the next boot-time backlog scan.
- Comparison is always wall-clock against `datetime`; no timezone/DST math in v1.

### 8. Audio Cue
- Optional bundled WAV plays on popup when `sound=true` in state (default on).
  Stored under `scheduler/assets/cue.wav`. Must not crash if file is missing.

### 9. Concurrent Edit Conflicts (Obsidian Safety)
- All writes are line-anchored: the parser stores `(file, exact_line_text)`. Before any
  write, the app re-reads the file; it rewrites ONLY the physical source line whose
  content matches the anchor exactly. If the line moved or changed, it retries once
  then aborts silently, leaving the user's edit untouched.

### 10. Multi-Monitor Placement
- Popup centers on the monitor containing the cursor; falls back to primary screen.

### 11. Penalty Mechanic Substance
- Persistent integer `penalty_count` in state, incremented by 1 for each missed task a
  user accepts in the backlog. Never auto-decrements. Reset is manual only, in the
  backlog header via a hold-to-confirm button.
- Pure cosmetic friction (displayed as the SCHEDULER panel's penalty counter) — never blocks or cancels work.