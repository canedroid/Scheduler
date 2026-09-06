"""The "MISSED TASKS" backlog review screen shown at boot (addendum §2, §11).

Frameless dark-gray card listing every missed task chronologically with its
lateness, a live SCHEDULER counter, an Accept button that records one
penalty per task, and a hold-to-confirm penalty reset.
"""
from __future__ import annotations

import logging

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QLinearGradient, QColor, QPen
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from scheduler import config
from scheduler.models import MissedTask
from scheduler.ui import theme

log = logging.getLogger(__name__)

BACKLOG_WIDTH = 470
HOLD_MS = 1500


class BacklogWindow(QWidget):
    accepted = pyqtSignal(int)   # penalties to record
    reset = pyqtSignal()         # reset penalty counter

    def __init__(self, missed: list[MissedTask], penalty_count: int = 0, initial: bool = False):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self._missed = missed
        self._penalty_count = penalty_count
        self._initial = initial
        self._reset_armed = False

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
        self.setFixedSize(BACKLOG_WIDTH, 420)
        self.setWindowOpacity(config.WINDOW_OPACITY)
        self.setGraphicsEffect(theme.glow(self, config.PURPLE, blur=52, alpha=245))
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 20)
        root.setSpacing(10)

        # header ---------------------------------------------------------------
        title = QLabel("SCHEDULER", self)
        title.setFont(theme.header_font(17))
        title.setStyleSheet(f"color: {config.PURPLE_GLOW}; background: transparent;")
        title.setGraphicsEffect(theme.glow(title, config.PURPLE, blur=20, alpha=210))
        root.addWidget(title)

        subtitle = QLabel(self)
        subtitle.setText(f"MISSED TASKS  {len(self._missed)}   ·   PENALTY  {self._penalty_count}")
        subtitle.setFont(theme.header_font(12))
        subtitle.setStyleSheet(f"color: {config.DANGER}; background: transparent;")
        subtitle.setObjectName("penaltyLabel")
        root.addWidget(subtitle)
        self._penalty_label = subtitle

        notice = QLabel(self)
        if self._initial:
            notice.setText(f"{len(self._missed)} unchecked task{'' if len(self._missed) == 1 else 's'} left in the past.")
        else:
            notice.setText(f"{len(self._missed)} missed task{'' if len(self._missed) == 1 else 's'} requiring review.")
        notice.setFont(theme.body_font(10))
        notice.setStyleSheet(f"color: {config.TEXT_DIM}; background: transparent;")
        root.addWidget(notice)

        # list ------------------------------------------------------------------
        self._list = QListWidget(self)
        self._list.setStyleSheet(theme.scrollbar_qss())
        self._list.setFont(theme.body_font(12))
        for item in self._missed:
            self._list.addItem(
                f"{item.scheduled_time}  │  {item.task.description}      (late {item.lateness})"
            )
        root.addWidget(self._list, stretch=1)

        # footer -----------------------------------------------------------------
        footer = QHBoxLayout()

        reset_btn = QPushButton("RESET PENALTY  (hold 1.5s)", self)
        reset_btn.setStyleSheet(theme.button_qss(config.TEXT_DIM, "rgba(230, 230, 230, 30)"))
        reset_btn.setMinimumHeight(36)
        reset_btn.pressed.connect(self._arm_reset)
        reset_btn.released.connect(self._disarm_reset)
        self._reset_btn = reset_btn
        self._reset_timer = QTimer(self)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.setInterval(HOLD_MS)
        self._reset_timer.timeout.connect(self._do_reset)

        accept_btn = QPushButton("ACCEPT & CONTINUE", self)
        accept_btn.setStyleSheet(theme.button_qss(config.PURPLE_GLOW, "rgba(200, 200, 200, 40)"))
        accept_btn.setMinimumHeight(36)
        accept_btn.setMinimumWidth(220)
        accept_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        accept_btn.clicked.connect(self._accept)

        hint = QLabel("A missed task is recorded once.", self)
        hint.setFont(theme.body_font(9))
        hint.setStyleSheet(f"color: {config.TEXT_DIM}; background: transparent;")
        footer.addWidget(reset_btn)
        footer.addWidget(hint)
        footer.addStretch(1)
        footer.addWidget(accept_btn)
        root.addLayout(footer)

    # -- painting -------------------------------------------------------------- #
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

        top_line = QColor(config.PURPLE_GLOW)
        top_line.setAlpha(170)
        painter.setPen(QPen(top_line, 1.5))
        painter.drawLine(rect.left() + 20, rect.top() + 2, rect.right() - 20, rect.top() + 2)

    # -- actions ---------------------------------------------------------------- #
    def _accept(self) -> None:
        self.accepted.emit(len(self._missed) if self._initial else 0)
        self.close()

    def _arm_reset(self) -> None:
        self._reset_armed = True
        self._reset_btn.setText("CONFIRM RESET…")
        self._reset_timer.start()

    def _disarm_reset(self) -> None:
        self._reset_armed = False
        self._reset_timer.stop()
        self._reset_btn.setText("RESET PENALTY  (hold 1.5s)")

    def _do_reset(self) -> None:
        if self._reset_armed:
            self._disarm_reset()
            self.reset.emit()

    def set_penalty_count(self, count: int) -> None:
        self._penalty_count = count
        self._penalty_label.setText(f"MISSED TASKS  {len(self._missed)}   ·   PENALTY  {count}")

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape):
            self._accept()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        log.debug("Backlog closed with %d tasks shown", len(self._missed))
        super().closeEvent(event)