# Project Scheduler — Benchmarks

Tested 2026-09-06 on Windows (Python 3.11.0, PyQt6 6.11.0).

## Runtime footprint (idle in system tray)

| Metric            | Value     |
|-------------------|-----------|
| RAM (working set) | ~41 MB    |
| Threads           | 5         |
| Open handles      | ~218      |
| CPU (idle)        | 0%        |

Polling interval: 10 seconds. Each poll classifies all tasks in under 1 ms.

## Operation benchmarks (600 tasks across 30 daily files)

| Operation                            | Median   | Best     |
|--------------------------------------|----------|----------|
| **read_all_tasks** (full vault)      | 12.18 ms | 7.82 ms  |
| **read_tasks** (1 day, 20 tasks)    | 0.20 ms  | 0.19 ms  |
| **classify x600** (1 poll cycle)     | 0.67 ms  | 0.55 ms  |
| **find_due_tasks** (1 poll cycle)    | 0.60 ms  | 0.53 ms  |
| **aggregate_missed** (boot scan)     | 11.49 ms | 9.91 ms  |
| **add_task** (append to file)        | 0.89 ms  | 0.89 ms  |
| **complete_task** (line-anchor)      | 0.75 ms  | 0.75 ms  |
| **delete_task** (line-anchor)        | 0.63 ms  | 0.63 ms  |
| **state.save** (200 fired hashes)    | 1.37 ms  | 1.33 ms  |
| **StateStore load** (200 hashes)     | 0.26 ms  | 0.17 ms  |

## Storage

600 tasks across 30 `.md` files consume ~18 KB total markdown.
`state.json` with 200 fired-task hashes: ~4 KB.

## Summary

- One poll cycle classifies 600 tasks in under 1 ms — budget is 10,000 ms.
- Full vault read (30 days) under 13 ms.
- Every write (add / complete / delete) under 1 ms — line-anchored, conflict-safe.
- Idle process stays below 45 MB RAM with zero CPU.
- At scale: the system comfortably handles 5,000+ tasks before any poll interval concern.
