"""Central configuration: paths, timing rules, theme palette, and the task-line contract."""
from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

VAULT_DIR = PROJECT_ROOT / "vault"
STATE_FILE = PROJECT_ROOT / "scheduler_state.json"
ASSETS_DIR = PROJECT_ROOT / "scheduler" / "assets"
CUE_WAV = ASSETS_DIR / "cue.wav"

# --------------------------------------------------------------------------- #
# Timing                                                                       #
# --------------------------------------------------------------------------- #
POLL_INTERVAL_SECONDS = 10
GRACE_MINUTES = 15
POPUP_DURATION_MS = 20_000
SNOOZE_OPTIONS_MIN = (5, 15, 30)

# --------------------------------------------------------------------------- #
# Markdown contract (see SYSTEM_SPEC addendum sections 1 & 3)                  #
# --------------------------------------------------------------------------- #
RAW_TASK_PATTERN = r"^\s*-\s\[([ xX])\]\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(\|\s*)?(.*)$"
TASK_LINE_RE = re.compile(RAW_TASK_PATTERN)

CHECKBOX_COMPLETE_RE = re.compile(r"(\s*-\s)\[ \]")
CHECKBOX_SNOOZE_RE = re.compile(r"^(\s*-\s\[ \])\s+(\d{1,2}):(\d{2})(?::(\d{2}))?(.*)$")

DATE_FILE_FORMAT = "%Y-%m-%d"


def task_filename(day) -> str:
    """Return the canonical per-day markdown filename."""
    return f"{day:{DATE_FILE_FORMAT}}.md"


def is_dated_filename(path: Path) -> bool:
    """True if the file stem parses as a YYYY-MM-DD date."""
    try:
        __import__("datetime").datetime.strptime(path.stem, DATE_FILE_FORMAT)
        return True
    except ValueError:
        return False


# --------------------------------------------------------------------------- #
# Theme (monochrome HUD — white, black, and shades of gray)                     #
# --------------------------------------------------------------------------- #
PURPLE = "#c9c9c9"
PURPLE_SOFT = "#3b3b3b"
PURPLE_GLOW = "#ececec"
BG_GLASS = "#0e0e0e"
BG_GLASS_STRONG = "#1c1c1c"
TEXT = "#f5f5f5"
TEXT_DIM = "#a8a8a8"
DANGER = "#e0e0e0"
SUCCESS = "#9a9a9a"
WARNING = "#c0c0c0"

FONT_FAMILY = "Segoe UI"
FONT_FAMILY_HEADER = "Bahnschrift"

WINDOW_OPACITY = 0.75