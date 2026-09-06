"""Month-view calendar: shows pending-task counts and range-event coverage.

Deliberately never auto-shown — it is opened on demand from the tray. Clicking
a date activates the planner on that day.
"""
from __future__ import annotations

import calendar as _calendar
import logging
from datetime import date
from pathlib import Path

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPen, QGuiApplication
from PyQt6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from scheduler import config
from scheduler.calendar import month_counts, month_matrix, range_covered_days
from scheduler.markdown_parser import read_all_events, read_all_tasks
from scheduler.ui import theme

log = logging.getLogger(__name__)

WEEK_HEADERS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
CALENDAR_WIDTH = 640
CALENDAR_HEIGHT = 560


class CalendarWindow(QWidget):
    """Frameless month grid; `dayActivated` fires with the clicked `date`."""

    dayActivated = pyqtSignal(object)

    def __init__(self, vault: Path, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool,
        )
        self._vault = Path(vault)
        today = date.today()
        self._year = today.year
        self._month = today.month
        self._counts: dict[date, int] = {}
        self._covered: set[date] = set()
        self._settings: "QWidget | None" = None
        self._opacity_saved = None

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(CALENDAR_WIDTH, CALENDAR_HEIGHT)
        theme.bind_opacity(self)
        self.setGraphicsEffect(theme.glow(self, config.PURPLE, blur=52, alpha=245))
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------ UI #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 20, 26, 18)
        root.setSpacing(10)

        header = QHBoxLayout()
        glyph = QLabel("◈", self)
        glyph.setStyleSheet(f"color: {config.PURPLE_GLOW}; font-size: 20px; background: transparent;")
        title = QLabel("CALENDAR", self)
        title.setFont(theme.header_font(17))
        title.setStyleSheet(f"color: {config.PURPLE_GLOW}; background: transparent;")
        title.setGraphicsEffect(theme.glow(title, config.PURPLE, blur=20, alpha=210))
        header.addWidget(glyph)
        header.addWidget(title)
        header.addStretch(1)

        self._month_label = QLabel(self)
        self._month_label.setFont(theme.header_font(13))
        self._month_label.setStyleSheet(f"color: {config.TEXT}; background: transparent;")

        back_btn = QPushButton("◂", self)
        fwd_btn = QPushButton("▸", self)
        today_btn = QPushButton("TODAY", self)
        settings_btn = QPushButton("⚙", self)
        settings_btn.setToolTip("Settings — transparency")
        close_btn = QPushButton("✕", self)
        close_btn.setToolTip("Close calendar")
        for button, outline in (
            (back_btn, config.TEXT_DIM),
            (fwd_btn, config.TEXT_DIM),
            (today_btn, config.PURPLE_GLOW),
            (settings_btn, config.PURPLE_GLOW),
            (close_btn, config.TEXT_DIM),
        ):
            button.setStyleSheet(theme.button_qss(outline, "rgba(200, 200, 200, 30)", padding="4px 12px"))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(lambda: self._shift_month(-1))
        fwd_btn.clicked.connect(lambda: self._shift_month(1))
        today_btn.clicked.connect(self._jump_today)
        settings_btn.clicked.connect(self._open_settings)
        close_btn.clicked.connect(self._hide_self)
        header.addWidget(self._month_label)
        header.addWidget(back_btn)
        header.addWidget(fwd_btn)
        header.addWidget(today_btn)
        header.addWidget(settings_btn)
        header.addWidget(close_btn)
        root.addLayout(header)

        week_row = QGridLayout()
        week_row.setSpacing(6)
        for index, label in enumerate(WEEK_HEADERS):
            cell = QLabel(label, self)
            cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell.setStyleSheet(f"color: {config.TEXT_DIM}; font-size: 10px; background: transparent;")
            week_row.addWidget(cell, 0, index)
        root.addLayout(week_row)

        self._grid = QGridLayout()
        self._grid.setSpacing(6)
        root.addLayout(self._grid, stretch=1)

        hint = QLabel("Click a day to open the planner on it.  ·  = tasks   ▮ = multi-day event", self)
        hint.setFont(theme.body_font(9))
        hint.setStyleSheet(f"color: {config.TEXT_DIM}; background: transparent;")
        root.addWidget(hint)

    def _cell_qss(self, day: date, count: int, covered: bool) -> str:
        borders = "border: 1px solid transparent;"
        if day == date.today():
            borders = f"border: 1px solid {config.PURPLE_GLOW};"
        color = config.TEXT if day == date.today() else config.TEXT_DIM
        return (
            f"QPushButton {{ color: {color}; background: rgba(200, 200, 200, 16); {borders}"
            f" border-radius: 8px; font-size: 12px; padding: 4px; text-align: center; }}"
            f"QPushButton:hover {{ background: rgba(220, 220, 220, 40); }}"
            + (f"QPushButton {{ border-bottom: 2px solid {config.PURPLE_GLOW}; }}" if covered else "")
        )

    def _rebuild_grid(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for index, day in enumerate(month_matrix(self._year, self._month)):
            row, col = divmod(index, 7)
            if day is None:
                placeholder = QLabel("", self)
                self._grid.addWidget(placeholder, row, col)
                continue
            count = self._counts.get(day, 0)
            covered = day in self._covered
            marks = ""
            if count:
                marks += f"·{count}"
            elif covered:
                marks += "▮"
            else:
                marks = "·"
            button = QPushButton(f"{day.day}\n{marks}", self)
            button.setProperty("_day", day)
            button.setStyleSheet(self._cell_qss(day, count, covered))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedHeight(52)
            button.clicked.connect(lambda _checked=False, d=day: self.dayActivated.emit(d))
            self._grid.addWidget(button, row, col)
        self._grid.setRowStretch(6, 1)

    # ------------------------------------------------------------------ data #
    def refresh(self) -> None:
        tasks = read_all_tasks(self._vault)
        events = read_all_events(self._vault)
        self._counts = month_counts(tasks)
        self._covered = range_covered_days(events, self._year, self._month)
        self._month_label.setText(f"{_calendar.month_name[self._month]} {self._year}")
        self._rebuild_grid()

    def _shift_month(self, offset: int) -> None:
        new_month = self._month + offset
        year, month = self._year, new_month
        while month < 1:
            month += 12
            year -= 1
        while month > 12:
            month -= 12
            year += 1
        self._year, self._month = year, month
        self.refresh()

    def _jump_today(self) -> None:
        today = date.today()
        self._year, self._month = today.year, today.month
        self.refresh()

    def _open_settings(self) -> None:
        if self._settings is None:
            from scheduler.ui.settings_window import SettingsWindow

            self._settings = SettingsWindow()
            self._settings.saved.connect(self._settings_saved)
        self._settings.show_centered()

    def _settings_saved(self, opacity: float) -> None:
        on_saved = getattr(self, "_opacity_saved", None)
        if on_saved is not None:
            on_saved(opacity)

    def set_opacity_sink(self, callback) -> None:
        """Wire the settings dialog's 'saved' value to a persistent store."""
        self._opacity_saved = callback

    def _hide_self(self) -> None:
        self.hide()

    def select_day(self, day: date) -> None:
        """Open the planner on `day` (also exposes a programmatic entry point)."""
        self._year, self._month = day.year, day.month
        self.dayActivated.emit(day)

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

    def show_centered(self) -> None:
        primary = QGuiApplication.primaryScreen()
        geo = primary.availableGeometry() if primary else self.geometry()
        self.move(QPoint(geo.center().x() - CALENDAR_WIDTH // 2, geo.center().y() - CALENDAR_HEIGHT // 2))
        self.show()
        self.raise_()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming) — hide, never destroy
        event.ignore()
        self.hide()