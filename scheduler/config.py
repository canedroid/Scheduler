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
# Theme (Solo Leveling HUD — dark glass + purple glow)                         #
# --------------------------------------------------------------------------- #
PURPLE = "#9b51e0"
PURPLE_SOFT = "#6f2dbd"
PURPLE_GLOW = "#c77dff"
BG_GLASS = "#120c1c"
BG_GLASS_STRONG = "#1c122c"
TEXT = "#eae6ff"
TEXT_DIM = "#9c93b5"
DANGER = "#ff3860"
SUCCESS = "#5ff2a0"
WARNING = "#ffd166"

FONT_FAMILY = "Segoe UI"
FONT_FAMILY_HEADER = "Bahnschrift"