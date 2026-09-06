"""System tray presence for the background monitor (addendum section 5).

Right-click the tray icon (or left-click to open the planner) while the app
runs quietly — popups are the only other windows that ever appear.
"""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from scheduler import config
from scheduler.ui import theme

log = logging.getLogger(__name__)


def make_icon() -> QIcon:
    """Runtime-drawn tray icon: purple rounded plate with the '◈' gate glyph."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    painter.setBrush(QColor(config.PURPLE_SOFT))
    painter.setPen(QColor(config.PURPLE_GLOW).lighter(140))
    painter.drawRoundedRect(2, 2, 60, 60, 14, 14)

    painter.setPen(QColor(config.PURPLE_GLOW))
    font = QFont(config.FONT_FAMILY_HEADER, 34)
    font.setPixelSize(34)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "◈")
    painter.end()
    return QIcon(pixmap)


class SchedulerTray:
    """Wraps QSystemTrayIcon with the planner / backlog / quit menu."""

    def __init__(self, on_planner, on_backlog, on_quit):
        self._tray = QSystemTrayIcon(make_icon())
        self._tray.setToolTip("Project Scheduler — checkpoint monitor online")

        menu = QMenu()
        menu.setStyleSheet(
            f"QMenu {{ background-color: {config.BG_GLASS_STRONG}; color: {config.TEXT};"
            f" border: 1px solid {config.PURPLE}; border-radius: 8px; padding: 4px; }}"
            f"QMenu::item {{ padding: 6px 20px; }}"
            f"QMenu::item:selected {{ background-color: rgba(155, 81, 224, 70); }}"
            f"QMenu::separator {{ height: 1px; background: rgba(155, 81, 224, 90); margin: 4px 6px; }}"
        )

        planner_action = QAction("▣  Gate Planner", menu)
        planner_action.triggered.connect(lambda: on_planner())
        backlog_action = QAction("⚠  Missed Quests", menu)
        backlog_action.triggered.connect(lambda: on_backlog())
        menu.addSeparator()
        quit_action = QAction("✕  Quit", menu)
        quit_action.triggered.connect(lambda: on_quit())

        menu.addAction(planner_action)
        menu.addAction(backlog_action)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)
        self._on_planner = on_planner

        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray.show()

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # left-click
            self._on_planner()

    def hide(self) -> None:
        self._tray.hide()