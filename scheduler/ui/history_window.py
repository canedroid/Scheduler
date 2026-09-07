"""Past-schedules review screen: every task/event from days before today.

Opened on demand from the system tray. Lists each past day's unchecked
("missed") and completed items chronologically, newest day first, so the user
can audit what was scheduled on previous days.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from scheduler import config
from scheduler.markdown_parser import read_all_events, read_all_tasks
from scheduler.models import Event, Task
from scheduler.ui import theme
from scheduler.ui.glass import GlassShell

log = logging.getLogger(__name__)

HISTORY_WIDTH = 520
HISTORY_HEIGHT = 540
GLOW_BLUR = 52
GLOW_ALPHA = 245


class _HistoryCard(QWidget):
    """The glass card: chronological list of past schedules, day-headed."""

    def __init__(self, vault: Path):
        super().__init__()
        self._vault = Path(vault)
        self.setFixedSize(HISTORY_WIDTH, HISTORY_HEIGHT)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 20)
        root.setSpacing(10)

        title = QLabel("SCHEDULER", self)
        title.setFont(theme.header_font(17))
        title.setStyleSheet(f"color: {config.PURPLE_GLOW}; background: transparent;")
        title.setGraphicsEffect(theme.glow(title, config.PURPLE, blur=20, alpha=210))
        root.addWidget(title)

        self._subtitle = QLabel(self)
        self._subtitle.setFont(theme.header_font(12))
        self._subtitle.setStyleSheet(f"color: {config.TEXT}; background: transparent;")
        root.addWidget(self._subtitle)

        self._list = QListWidget(self)
        self._list.setStyleSheet(theme.scrollbar_qss())
        self._list.setFont(theme.body_font(11))
        self._list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        root.addWidget(self._list, stretch=1)

        hint = QLabel("Past schedules audit — days before today.  [ ] missed   [x] completed", self)
        hint.setFont(theme.body_font(9))
        hint.setStyleSheet(f"color: {config.TEXT_DIM}; background: transparent;")
        root.addWidget(hint)

    def refresh(self) -> None:
        today = date.today()
        tasks = [t for t in read_all_tasks(self._vault) if t.date < today]
        events = [e for e in read_all_events(self._vault) if e.start.date() < today]
        tasks.sort(key=lambda t: t.scheduled, reverse=True)
        events.sort(key=lambda e: e.start, reverse=True)

        combined: list[tuple[date, str, bool, str]] = []  # (day, line_text, missed, sort_key)
        for task in tasks:
            combined.append((task.date, self._task_text(task), not task.done, f"T|{task.scheduled.isoformat()}"))
        for event in events:
            combined.append((event.start.date(), self._event_text(event), not event.done, f"E|{event.start.isoformat()}"))

        combined.sort(key=lambda row: row[3], reverse=True)

        self._list.clear()
        missed = sum(1 for row in combined if row[2])
        self._subtitle.setText(f"PAST SCHEDULES  {len(combined)}   ·   MISSED  {missed}")

        current_day: date | None = None
        for day, text, is_missed, _sort in combined:
            if day != current_day:
                current_day = day
                header_text = self._day_label(day, today)
                header_item = QListWidgetItem(header_text)
                header_item.setFont(theme.body_font(9, bold=True))
                header_item.setForeground(theme.PURPLE_GLOW)
                header_item.setFlags(Qt.ItemFlag.NoItemFlags)
                self._list.addItem(header_item)
            item = QListWidgetItem()
            item.setText(text)
            item.setForeground(theme.DANGER if is_missed else theme.TEXT_DIM)
            self._list.addItem(item)

    # ------------------------------------------------------------------ text #
    @staticmethod
    def _day_label(day: date, today: date) -> str:
        if day == today - timedelta(days=1):
            return f"— {day:%A, %b %d}  (yesterday) —"
        return f"— {day:%A, %b %d} —"

    @staticmethod
    def _task_text(task: Task) -> str:
        marker = "[x]  " if task.done else "[ ]  "
        return f"{task.time:%H:%M}  {marker}{task.description}"

    @staticmethod
    def _event_text(event: Event) -> str:
        marker = "[x]  " if event.done else "[ ]  "
        return f"{event.start:%H:%M}–{event.end:%H:%M}  {marker}◈ {event.title}"

    # ------------------------------------------------------------------ paint #
    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0.0, QColor(38, 38, 38, 255))
        gradient.setColorAt(0.6, QColor(22, 22, 22, 255))
        gradient.setColorAt(1.0, QColor(16, 16, 16, 255))
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor(config.PURPLE_GLOW), 1))
        painter.drawRoundedRect(rect, 16, 16)
        top = QColor(config.PURPLE_GLOW)
        top.setAlpha(170)
        painter.setPen(QPen(top, 1.5))
        painter.drawLine(rect.left() + 20, rect.top() + 2, rect.right() - 20, rect.top() + 2)


class HistoryWindow(GlassShell):
    """Mounts the past-schedules card inside a glass shell."""

    def __init__(self, vault: Path, parent=None):
        super().__init__(HISTORY_WIDTH, HISTORY_HEIGHT, GLOW_BLUR, GLOW_ALPHA)
        card = _HistoryCard(vault)
        self.mount(card, GLOW_BLUR, GLOW_ALPHA)

    def refresh(self) -> None:
        self.card.refresh()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming) — hide, never destroy
        event.ignore()
        self.hide()