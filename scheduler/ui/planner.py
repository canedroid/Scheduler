"""The Scheduler panel: frameless HUD-styled panel for adding and managing tasks.

Add tasks for any day (creates/updates the YYYY-MM-DD.md file), or manage the
day's existing tasks: edit the time inline, mark a task complete, or delete a
task. Every action flows through the line-anchored parser and re-reads the file
afterwards, so external Obsidian edits are always respected.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time
from pathlib import Path

from PyQt6.QtCore import QDate, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import (
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from scheduler import config
from scheduler.markdown_parser import add_task, complete_task, delete_task, read_tasks, reschedule_task
from scheduler.models import Task
from scheduler.ui import theme

log = logging.getLogger(__name__)

PLANNER_WIDTH = 520
PLANNER_HEIGHT = 640
STATUS_MS = 2600


class GatePlanner(QWidget):
    """Full control panel for a day's tasks (add / reschedule / complete / delete)."""

    tasks_changed = pyqtSignal()  # so the host can resync (e.g. backlog titles)

    def __init__(self, vault: Path, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool,
        )
        self._vault = Path(vault)
        self._tasks: list[Task] = []
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self._clear_status)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(PLANNER_WIDTH, PLANNER_HEIGHT)
        self.setWindowOpacity(config.WINDOW_OPACITY)
        self.setGraphicsEffect(theme.glow(self, config.PURPLE, blur=52, alpha=245))
        self._build_ui()
        self._refresh()

    # ------------------------------------------------------------------ UI #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 20, 26, 18)
        root.setSpacing(10)

        # header -------------------------------------------------------------
        header = QHBoxLayout()
        title = QLabel("SCHEDULER", self)
        title.setFont(theme.header_font(17))
        title.setStyleSheet(f"color: {config.PURPLE_GLOW}; background: transparent;")
        title.setGraphicsEffect(theme.glow(title, config.PURPLE, blur=20, alpha=210))

        close_btn = QPushButton("✕", self)
        close_btn.setStyleSheet(
            f"color: {config.TEXT_DIM}; background: transparent; border: none;"
            f"font-size: 16px; padding: 2px 8px;"
        )
        close_btn.clicked.connect(self.close)

        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(close_btn)
        root.addLayout(header)

        # day picker ---------------------------------------------------------
        day_row = QHBoxLayout()
        day_label = QLabel("DAY", self)
        day_label.setFont(theme.body_font(10, bold=True))
        day_label.setStyleSheet(f"color: {config.TEXT_DIM}; background: transparent;")

        self._date_edit = QDateEdit(QDate.currentDate(), self)
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("yyyy-MM-dd")
        self._date_edit.dateChanged.connect(self._refresh)
        self._date_edit.setStyleSheet(_input_qss())
        day_row.addWidget(day_label)
        day_row.addWidget(self._date_edit)
        day_row.addStretch(1)
        root.addLayout(day_row)

        # add form -------------------------------------------------------------
        form = QHBoxLayout()
        self._time_edit = QTimeEdit(time(9, 0), self)
        self._time_edit.setDisplayFormat("HH:mm")
        self._time_edit.setStyleSheet(_input_qss())

        self._desc_edit = QLineEdit(self)
        self._desc_edit.setPlaceholderText("What does the task require?")
        self._desc_edit.setStyleSheet(_input_qss())
        self._desc_edit.returnPressed.connect(self._add_task)

        add_btn = QPushButton("ADD TASK", self)
        add_btn.setStyleSheet(theme.button_qss(config.PURPLE_GLOW, "rgba(200, 200, 200, 40)"))
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._add_task)

        form.addWidget(self._time_edit)
        form.addWidget(self._desc_edit, stretch=1)
        form.addWidget(add_btn)
        root.addLayout(form)

        # warning / status -----------------------------------------------------
        self._status_label = QLabel(self)
        self._status_label.setFont(theme.body_font(10))
        self._status_label.setStyleSheet(f"color: {config.DANGER}; background: transparent;")
        self._status_label.hide()
        root.addWidget(self._status_label)

        # tasks section ---------------------------------------------------------
        section = QHBoxLayout()
        self._section_label = QLabel(self)
        self._section_label.setFont(theme.body_font(10, bold=True))
        self._section_label.setStyleSheet(f"color: {config.TEXT_DIM}; background: transparent;")
        section.addWidget(self._section_label)
        section.addStretch(1)
        root.addLayout(section)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; }")
        self._rows_host = QWidget(self._scroll)
        self._rows_layout = QVBoxLayout(self._rows_host)
        self._rows_layout.setContentsMargins(0, 0, 6, 0)
        self._rows_layout.setSpacing(8)
        self._scroll.setWidget(self._rows_host)
        root.addWidget(self._scroll, stretch=1)

        # footer hint ------------------------------------------------------------
        hint = QLabel("Changing a time, checkbox, or delete rewrites the markdown safely (line-anchored).", self)
        hint.setFont(theme.body_font(9))
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {config.TEXT_DIM}; background: transparent;")
        root.addWidget(hint)

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

    # ------------------------------------------------------------------ logic #
    def _current_day(self) -> date:
        return self._date_edit.date().toPyDate()

    def _add_task(self) -> None:
        description = self._desc_edit.text().strip()
        if not description:
            self._set_status("A task needs a description.", is_error=True)
            return
        task_time = self._time_edit.time().toPyTime()
        if add_task(self._vault, self._current_day(), task_time, description):
            self._desc_edit.clear()
            self._desc_edit.setFocus()
            self._set_status(f"TASK ADDED  {task_time:%H:%M}  —  {description}", is_error=False)
            self._refresh()
            self.tasks_changed.emit()
        else:
            self._set_status("Could not write the task file. Check permissions.", is_error=True)

    def _apply_reschedule(self, task: Task, edit: QTimeEdit) -> None:
        new_time = edit.time().toPyTime()
        if new_time == task.time:
            return
        if reschedule_task(self._vault, task, new_time):
            self._set_status(f"MOVED → {new_time:%H:%M}  |  {task.description}", is_error=False)
            self._refresh()
            self.tasks_changed.emit()
        else:
            self._refresh()  # anchor may have moved after an external edit

    def _task_done(self, task: Task) -> None:
        if complete_task(self._vault, task):
            self._set_status(f"TASK COMPLETED  |  {task.description}", is_error=False)
            self._refresh()
            self.tasks_changed.emit()

    def _task_delete(self, task: Task) -> None:
        if delete_task(self._vault, task):
            self._set_status(f"TASK DELETED  |  {task.description}", is_error=False)
            self._refresh()
            self.tasks_changed.emit()

    def _refresh(self) -> None:
        day = self._current_day()
        all_tasks = read_tasks(self._vault, day)
        self._tasks = [t for t in all_tasks if not t.done]
        done_count = len(all_tasks) - len(self._tasks)
        self._clear_rows()
        self._section_label.setText(f"TASKS · {config.task_filename(day)}  ({len(self._tasks)})")
        if not self._tasks:
            if done_count:
                msg = f"All {done_count} task{'s' if done_count != 1 else ''} completed for this day."
            else:
                msg = "No tasks for this day yet — add one above."
            empty = QLabel(msg, self._rows_host)
            empty.setStyleSheet(f"color: {config.TEXT_DIM}; background: transparent; padding: 12px;")
            self._rows_layout.addWidget(empty)
            return
        for task in self._tasks:
            self._rows_layout.addWidget(self._make_row(task))
        self._rows_layout.addStretch(1)

    def _clear_rows(self) -> None:
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _make_row(self, task: Task) -> QWidget:
        row = QWidget(self._rows_host)
        row.setStyleSheet("background: rgba(200, 200, 200, 14); border-radius: 8px;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        time_edit = QTimeEdit(task.time, row)
        time_edit.setDisplayFormat("HH:mm")
        time_edit.setStyleSheet(
            f"QTimeEdit {{ color: {config.PURPLE_GLOW}; background: rgba(28, 28, 28, 160);"
            f" border: 1px solid {config.PURPLE}; border-radius: 6px; padding: 3px 6px; }}"
        )
        time_edit.editingFinished.connect(lambda t=task, e=time_edit: self._apply_reschedule(t, e))

        desc = QLabel(task.description, row)
        desc.setWordWrap(True)
        desc.setFont(theme.body_font(12))
        desc.setStyleSheet("color: %s; background: transparent;" % config.TEXT)
        if task.done:
            desc.setStyleSheet(f"color: {config.TEXT_DIM}; background: transparent; text-decoration: line-through;")

        done_btn = QPushButton("✓", row)
        done_btn.setToolTip("Mark complete")
        done_btn.setStyleSheet(
            f"QPushButton {{ color: {config.SUCCESS}; background: transparent; border: 1px solid {config.SUCCESS};"
            f" border-radius: 6px; padding: 4px 8px; }}"
            f"QPushButton:hover {{ background: rgba(200, 200, 200, 25); }}"
        )
        done_btn.clicked.connect(lambda t=task: self._task_done(t))

        del_btn = QPushButton("✕", row)
        del_btn.setToolTip("Delete task")
        del_btn.setStyleSheet(
            f"QPushButton {{ color: {config.DANGER}; background: transparent; border: 1px solid rgba(230, 230, 230, 120);"
            f" border-radius: 6px; padding: 4px 8px; }}"
            f"QPushButton:hover {{ background: rgba(230, 230, 230, 30); }}"
        )
        del_btn.clicked.connect(lambda t=task: self._task_delete(t))

        layout.addWidget(time_edit)
        layout.addWidget(desc, stretch=1)
        layout.addWidget(done_btn)
        layout.addWidget(del_btn)
        return row

    # ------------------------------------------------------------------ status #
    def _set_status(self, message: str, is_error: bool = False) -> None:
        color = config.DANGER if is_error else config.PURPLE_GLOW
        self._status_label.setStyleSheet(f"color: {color}; background: transparent;")
        self._status_label.setText(message)
        self._status_label.show()
        self._status_timer.start(STATUS_MS)

    def _clear_status(self) -> None:
        self._status_label.hide()

    # ------------------------------------------------------------------ geom #
    def show_centered(self) -> None:
        from PyQt6.QtGui import QGuiApplication

        geo = QGuiApplication.primaryScreen()
        screen = geo.availableGeometry() if geo else self.geometry()
        self.move(screen.center().x() - PLANNER_WIDTH // 2, screen.center().y() - PLANNER_HEIGHT // 2)
        self.show()
        self.raise_()

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming) — hide, never destroy
        event.ignore()
        self.hide()


def _input_qss() -> str:
    return (
        f"QLineEdit, QDateEdit, QTimeEdit {{"
        f" color: {config.TEXT}; background: rgba(28, 28, 28, 140);"
        f" border: 1px solid rgba(220, 220, 220, 160); border-radius: 8px; padding: 6px 10px; }}"
        f"QLineEdit:focus, QDateEdit:focus, QTimeEdit:focus {{ border: 1px solid {config.PURPLE_GLOW}; }}"
        f"QDateEdit::drop-down, QTimeEdit::drop-down {{ border: none; }}"
        f"QDateEdit::down-arrow {{ image: none; width: 0; }}"
        f"QCalendarWidget QWidget {{ alternate-background-color: {config.BG_GLASS}; }}"
        f"QCalendarWidget QAbstractItemView {{ background: {config.BG_GLASS_STRONG};"
        f" color: {config.TEXT}; selection-background-color: {config.PURPLE_SOFT}; }}"
        f"QCalendarWidget QToolButton {{ color: {config.PURPLE_GLOW};"
        f" background: transparent; padding: 4px; border-radius: 6px; }}"
    )