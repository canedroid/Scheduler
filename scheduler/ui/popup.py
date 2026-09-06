"""The floating system notification: frameless, translucent dark-glass card with
a glowing gray border that mimics a system pop-up (addendum sections 4 & 6).

Pure toast semantics by default: stays on top, never steals input focus, and
auto-hides after 20 seconds. Clicking the glass (outside the buttons) dismisses
the task; every action rewrites the source markdown via the parser.
"""
from __future__ import annotations

import logging
from datetime import datetime

from PyQt6.QtCore import QPoint, QRect, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QCloseEvent,
    QColor,
    QCursor,
    QGuiApplication,
    QPainter,
    QPen,
)
from PyQt6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from scheduler import config
from scheduler.models import Event, Task
from scheduler.ui import theme

log = logging.getLogger(__name__)

DIALOG_WIDTH = 400
DIALOG_HEIGHT = 212


class SystemPopup(QWidget):
    completed = pyqtSignal(object)        # Task
    snoozed = pyqtSignal(object, int)     # Task, minutes
    dismissed = pyqtSignal(object)        # Task

    def __init__(self, task: Task, late: bool = False, force_focus: bool = False):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self._task = task
        self._late = late
        self._closed = False

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, not force_focus)
        if not force_focus:
            self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)

        self.setFixedSize(DIALOG_WIDTH, DIALOG_HEIGHT)
        self.setWindowOpacity(config.WINDOW_OPACITY)
        self.setGraphicsEffect(theme.glow(self, config.PURPLE, blur=48, alpha=235))
        self._build_ui()

        self._auto_hide = QTimer(self)
        self._auto_hide.setSingleShot(True)
        self._auto_hide.timeout.connect(self.dismiss)
        self._auto_hide.start(config.POPUP_DURATION_MS)

    # -- construction -------------------------------------------------------- #
    def _build_ui(self) -> None:
        header, _body = theme.font_families()
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 16)
        root.setSpacing(8)

        # header row ---------------------------------------------------------
        top = QHBoxLayout()
        icon = QLabel("◈", self)
        icon.setStyleSheet(f"color: {config.PURPLE_GLOW}; font-size: 22px; background: transparent;")
        title = QLabel(self)
        title.setText("SCHEDULER")
        title.setFont(theme.header_font(15))
        title.setStyleSheet(f"color: {config.PURPLE_GLOW}; background: transparent;")
        title.setGraphicsEffect(theme.glow(title, config.PURPLE, blur=18, alpha=200))

        badge = QLabel(self)
        if self._late:
            badge.setText("LATE")
            badge.setStyleSheet(
                f"color: {config.TEXT}; background: rgba(230, 230, 230, 30);"
                f"border: 1px solid {config.DANGER}; border-radius: 10px; padding: 1px 9px;"
            )
        else:
            badge.setText(self._task.scheduled.strftime("%H:%M"))
            badge.setStyleSheet(
                f"color: {config.PURPLE_GLOW}; background: rgba(200, 200, 200, 40);"
                f"border: 1px solid {config.PURPLE}; border-radius: 10px; padding: 1px 9px;"
            )
        badge.setFont(theme.body_font(11, bold=True))
        top.addWidget(icon)
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(badge)
        root.addLayout(top)

        # description --------------------------------------------------------
        desc = QLabel(self)
        desc.setText(self._task.description)
        desc.setWordWrap(True)
        desc.setFont(theme.body_font(13))
        desc.setStyleSheet(f"color: {config.TEXT}; background: transparent;")
        desc.setMaximumHeight(64)
        root.addWidget(desc)

        if self._late:
            note = QLabel(self)
            note.setText("SCHEDULED TIME PASSED")
            note.setFont(theme.body_font(9))
            note.setStyleSheet(f"color: {config.TEXT_DIM}; background: transparent;")
            root.addWidget(note)

        root.addStretch(1)

        # buttons --------------------------------------------------------------
        rows = QHBoxLayout()
        rows.setSpacing(8)

        complete_btn = QPushButton("COMPLETE", self)
        complete_btn.setStyleSheet(theme.button_qss(config.SUCCESS, "rgba(200, 200, 200, 25)"))
        complete_btn.clicked.connect(self._complete)

        snooze_btn = QPushButton("SNOOZE", self)
        snooze_btn.setStyleSheet(theme.button_qss(config.PURPLE, "rgba(200, 200, 200, 30)"))
        snooze_btn.clicked.connect(self._snooze_menu)

        dismiss_btn = QPushButton("DISMISS", self)
        dismiss_btn.setStyleSheet(theme.button_qss(config.TEXT_DIM, "rgba(220, 220, 220, 25)"))
        dismiss_btn.clicked.connect(self.dismiss)

        for button in (complete_btn, snooze_btn, dismiss_btn):
            button.setMinimumHeight(34)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        rows.addStretch(1)
        rows.addWidget(complete_btn)
        rows.addWidget(snooze_btn)
        rows.addWidget(dismiss_btn)
        root.addLayout(rows)

    # -- painting ------------------------------------------------------------ #
    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPen

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0.0, QColor(38, 38, 38, 255))
        gradient.setColorAt(0.7, QColor(22, 22, 22, 255))
        gradient.setColorAt(1.0, QColor(16, 16, 16, 255))
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor(config.PURPLE_GLOW), 1, cap=Qt.PenCapStyle.SquareCap))
        painter.drawRoundedRect(rect, 14, 14)

        # inner glow accent along the top edge
        painter.setPen(QPen(QColor(config.PURPLE).lighter(120), 1.5))
        top_line = QColor(config.PURPLE_GLOW)
        top_line.setAlpha(170)
        painter.setPen(QPen(top_line, 1.5))
        painter.drawLine(rect.left() + 18, rect.top() + 2, rect.right() - 18, rect.top() + 2)

    # -- geometry ------------------------------------------------------------ #
    def show_centered(self) -> None:
        cursor = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor) or QGuiApplication.primaryScreen()
        if screen is None:
            self.center_on_screen()
        else:
            geo = screen.availableGeometry()
            target = QPoint(
                geo.center().x() - DIALOG_WIDTH // 2,
                geo.center().y() - DIALOG_HEIGHT // 2,
            )
            self.move(target)
        self.show()
        self.raise_()

    def center_on_screen(self) -> None:
        screen = QGuiApplication.primaryScreen()
        geo = screen.availableGeometry() if screen else self.geometry()
        self.move(geo.center().x() - DIALOG_WIDTH // 2, geo.center().y() - DIALOG_HEIGHT // 2)

    # -- actions ------------------------------------------------------------- #
    def _complete(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._auto_hide.stop()
        self.completed.emit(self._task)
        self._safe_close()

    def dismiss(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._auto_hide.stop()
        self.dismissed.emit(self._task)
        self._safe_close()

    def _snooze_menu(self) -> None:
        if self._closed:
            return
        button = self.sender() if isinstance(self.sender(), QPushButton) else None
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background-color: {config.BG_GLASS_STRONG}; color: {config.TEXT};"
            f" border: 1px solid {config.PURPLE}; border-radius: 8px; padding: 4px; }}"
            f"QMenu::item {{ padding: 6px 18px; }}"
            f"QMenu::item:selected {{ background-color: rgba(220, 220, 220, 70); }}"
        )
        for minutes in config.SNOOZE_OPTIONS_MIN:
            action = menu.addAction(f"Snooze +{minutes} min")
            action.triggered.connect(lambda _checked=False, m=minutes: self._snooze(m))
        menu.addSeparator()
        custom_action = menu.addAction("Custom…")
        custom_action.triggered.connect(self._custom_snooze)
        pos = button.mapToGlobal(button.rect().bottomLeft()) if button else QCursor.pos()
        menu.exec(pos)

    def _custom_snooze(self) -> None:
        if self._closed:
            return
        from PyQt6.QtWidgets import QInputDialog

        minutes, accepted = QInputDialog.getInt(self, "Custom snooze", "Minutes:", 10, 1, 180)
        if accepted:
            self._snooze(minutes)

    def _snooze(self, minutes: int) -> None:
        if self._closed:
            return
        self._closed = True
        self._auto_hide.stop()
        self.snoozed.emit(self._task, minutes)
        self._safe_close()

    def _safe_close(self) -> None:
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.close()

    # -- click-anywhere-to-dismiss (addendum section 6) ---------------------- #
    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self.dismiss()
        super().mousePressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt naming)
        log.debug("Popup closed for task %r", self._task.description)
        super().closeEvent(event)


def event_eta_text(start: datetime, now: datetime | None = None) -> str:
    """Human-positive advance notice, e.g. 'Starting tomorrow at 09:00'."""
    now = now or datetime.now()
    delta_days = (start.date() - now.date()).days
    if delta_days <= 0:
        return f"Starting today at {start:%H:%M}"
    if delta_days == 1:
        return f"Starting tomorrow at {start:%H:%M}"
    return f"Starting {start:%A} at {start:%H:%M}"


class EventReminderPopup(QWidget):
    """Advance-notice popup for a multi-day event inside its lead window."""

    dismissed = pyqtSignal()
    openPlanner = pyqtSignal()  # jump the scheduler panel to the event's day

    def __init__(self, event: Event, force_focus: bool = False, now: datetime | None = None):
        super().__init__()
        self._event = event
        self._closed = False
        now = now or datetime.now()
        self._eta = event_eta_text(event.start, now)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(DIALOG_WIDTH, DIALOG_HEIGHT)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        badge = QLabel("◈  REMINDER", self)
        badge.setStyleSheet(
            f"color: {config.PURPLE_GLOW}; background: transparent;"
            f" font-size: 11px; font-weight: bold; letter-spacing: 1px;"
        )
        title = QLabel("SCHEDULER", self)
        title.setStyleSheet(f"color: {config.TEXT_DIM}; background: transparent; font-size: 10px;")
        header.addWidget(badge)
        header.addStretch(1)
        header.addWidget(title)
        layout.addLayout(header)

        desc = QLabel(event.title, self)
        desc.setWordWrap(True)
        desc.setFont(theme.body_font(14, bold=True))
        desc.setStyleSheet(f"color: {config.TEXT}; background: transparent;")
        layout.addWidget(desc, stretch=1)

        note = QLabel(self._event_note(), self)
        note.setWordWrap(True)
        note.setFont(theme.body_font(10))
        note.setStyleSheet(f"color: {config.TEXT_DIM}; background: transparent;")
        layout.addWidget(note)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        planner_btn = QPushButton("▣  OPEN PLANNER", self)
        planner_btn.setStyleSheet(
            f"QPushButton {{ color: {config.BG_GLASS_STRONG}; background: {config.PURPLE_GLOW};"
            f" border: 1px solid {config.PURPLE_GLOW}; border-radius: 6px; padding: 6px 14px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {config.PURPLE}; }}"
        )
        planner_btn.clicked.connect(self._open_planner)
        ok_btn = QPushButton("OK", self)
        ok_btn.setStyleSheet(
            f"QPushButton {{ color: {config.TEXT}; background: transparent; border: 1px solid rgba(230, 230, 230, 120);"
            f" border-radius: 6px; padding: 6px 16px; }}"
            f"QPushButton:hover {{ background: rgba(230, 230, 230, 30); }}"
        )
        ok_btn.clicked.connect(self.dismiss)
        buttons.addWidget(planner_btn)
        buttons.addWidget(ok_btn)
        layout.addLayout(buttons)

        self._auto_hide = QTimer(self)
        self._auto_hide.setSingleShot(True)
        self._auto_hide.setInterval(config.POPUP_DURATION_MS)
        self._auto_hide.timeout.connect(self.dismiss)

        if force_focus:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            self._auto_hide.stop()

    def _event_note(self) -> str:
        if self._event.end.date() > self._event.start.date():
            return f"{self._eta} · until {self._event.end:%A, %d %b %H:%M}"
        return self._eta

    def show_centered(self) -> None:
        self._auto_hide.start()
        center = (
            QApplication.primaryScreen().availableGeometry().center()
            if QApplication.primaryScreen()
            else QRect(0, 0, 400, 300).center()
        )
        self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)
        self.show()
        self.raise_()

    def dismiss(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._auto_hide.stop()
        self.dismissed.emit()
        self._safe_close()

    def _open_planner(self) -> None:
        self._closed = True
        self._auto_hide.stop()
        self.openPlanner.emit()
        self._safe_close()

    def _safe_close(self) -> None:
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.close()

    # -- click-anywhere-to-dismiss ------------------------------------------- #
    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self.dismiss()
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(config.BG_GLASS_STRONG)))
        painter.setPen(QPen(QColor(config.PURPLE), 1))
        painter.setOpacity(config.WINDOW_OPACITY)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 14, 14)
        painter.end()