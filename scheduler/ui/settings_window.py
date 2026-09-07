"""Frameless settings dialog: live app-window transparency + spoken announcements.

The opacity slider drives `theme.set_opacity` so every open window (calendar,
planner, backlog) is re-tinted in real time; the value persists through
`StateStore.opacity` when the dialog is dismissed. The TTS checkbox toggles
spoken fire announcements, persisted through `StateStore.tts` on every change.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from scheduler import config
from scheduler.ui import theme
from scheduler.ui.glass import GlassShell

log = logging.getLogger(__name__)

SETTINGS_WIDTH = 360
SETTINGS_HEIGHT = 232
GLOW_BLUR = 40
GLOW_ALPHA = 235


class _SettingsCard(QWidget):
    """The glass card holding the live opacity slider and TTS toggle."""

    changed = pyqtSignal(float)   # emitted on every slider move (write-through)
    saved = pyqtSignal(float)     # emitted on dismiss (final persist)
    tts_toggled = pyqtSignal(bool)  # emitted immediately on toggle (write-through)

    def __init__(self, tts: bool = False):
        super().__init__()
        self.setFixedSize(SETTINGS_WIDTH, SETTINGS_HEIGHT)
        self._tts_initial = bool(tts)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 16, 22, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("SETTINGS", self)
        title.setFont(theme.header_font(15))
        title.setStyleSheet(f"color: {config.PURPLE_GLOW}; background: transparent;")
        sub = QLabel("╱ window transparency", self)
        sub.setFont(theme.body_font(9))
        sub.setStyleSheet(f"color: {config.TEXT_DIM}; background: transparent;")
        header.addWidget(title)
        header.addWidget(sub)
        header.addStretch(1)
        close_btn = QPushButton("✕", self)
        close_btn.setToolTip("Close settings")
        close_btn.setFixedWidth(30)
        close_btn.setStyleSheet(
            f"QPushButton {{ color: {config.TEXT_DIM}; background: rgba(200, 200, 200, 18);"
            f" border: 1px solid rgba(230, 230, 230, 120); border-radius: 6px; font-size: 13px; }}"
            f"QPushButton:hover {{ background: rgba(230, 230, 230, 30); }}"
        )
        close_btn.clicked.connect(self.dismiss)
        header.addWidget(close_btn)
        root.addLayout(header)

        self._value_label = QLabel(self)
        self._value_label.setFont(theme.header_font(12))
        self._value_label.setStyleSheet(f"color: {config.TEXT}; background: transparent;")
        root.addWidget(self._value_label)

        slider_row = QHBoxLayout()
        label_min = QLabel("ghost 10%", self)
        label_min.setFont(theme.body_font(9))
        label_min.setStyleSheet(f"color: {config.TEXT_DIM}; background: transparent;")
        slider = QSlider(Qt.Orientation.Horizontal, self)
        slider.setRange(10, 100)
        slider.setValue(round(theme.current_opacity() * 100))
        slider.setTickInterval(5)
        slider.setCursor(Qt.CursorShape.PointingHandCursor)
        slider.valueChanged.connect(self._on_slider)
        slider.setStyleSheet(
            f"QSlider::groove:horizontal {{ background: rgba(200, 200, 200, 60);"
            f" height: 4px; border-radius: 2px; }}"
            f"QSlider::handle:horizontal {{ background: {config.PURPLE_GLOW};"
            f" width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }}"
            f"QSlider::sub-page:horizontal {{ background: {config.PURPLE}; border-radius: 2px; }}"
        )
        label_max = QLabel("solid 100%", self)
        label_max.setFont(theme.body_font(9))
        label_max.setStyleSheet(f"color: {config.TEXT_DIM}; background: transparent;")
        slider_row.addWidget(label_min)
        slider_row.addWidget(slider, stretch=1)
        slider_row.addWidget(label_max)
        root.addLayout(slider_row)
        self._slider = slider

        tts_row = QVBoxLayout()
        check = QCheckBox("SPOKEN ANNOUNCEMENTS (TTS)", self)
        check.setChecked(self._tts_initial)
        check.setCursor(Qt.CursorShape.PointingHandCursor)
        check.setStyleSheet(
            f"QCheckBox {{ color: {config.TEXT}; background: transparent; font-size: 12px; }}"
            f"QCheckBox::indicator {{ width: 15px; height: 15px; border: 1px solid rgba(230, 230, 230, 120);"
            f" border-radius: 4px; background: rgba(200, 200, 200, 18); }}"
            f"QCheckBox::indicator:checked {{ background: {config.PURPLE_GLOW};"
            f" border-color: {config.PURPLE_GLOW}; }}"
        )
        check.toggled.connect(self.tts_toggled)
        tts_row.addWidget(check)
        tts_hint = QLabel("Say task descriptions aloud when they fire (Windows voice).", self)
        tts_hint.setFont(theme.body_font(9))
        tts_hint.setStyleSheet(f"color: {config.TEXT_DIM}; background: transparent;")
        tts_row.addWidget(tts_hint)
        root.addLayout(tts_row)
        self._tts_check = check

        hint = QLabel("Applies instantly to the calendar, planner and missed-task windows.", self)
        hint.setWordWrap(True)
        hint.setFont(theme.body_font(9))
        hint.setStyleSheet(f"color: {config.TEXT_DIM}; background: transparent;")
        root.addWidget(hint)
        root.addStretch(1)

        self._update_label()

    def _on_slider(self, value: int) -> None:
        opacity = value / 100.0
        theme.set_opacity(opacity)
        self._update_label()
        self.changed.emit(opacity)

    def _update_label(self) -> None:
        percent = round(theme.current_opacity() * 100)
        self._value_label.setText(f"TRANSPARENCY   {percent}%")

    def dismiss(self) -> None:
        self.saved.emit(theme.current_opacity())
        self.window().hide()

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.button() == Qt.MouseButton.RightButton:
            self.dismiss()
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0.0, QColor(38, 38, 38, 255))
        gradient.setColorAt(0.7, QColor(22, 22, 22, 255))
        gradient.setColorAt(1.0, QColor(16, 16, 16, 255))
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor(config.PURPLE_GLOW), 1))
        painter.drawRoundedRect(rect, 14, 14)
        painter.end()


class SettingsWindow(GlassShell):
    """Mounts the settings card inside a glass shell (glow stays off the top level)."""

    changed = pyqtSignal(float)   # emitted on every slider move (write-through)
    saved = pyqtSignal(float)     # emitted on dismiss (final persist)
    tts_toggled = pyqtSignal(bool)

    def __init__(self, vault: Path | None = None, tts: bool = False, parent=None):
        del vault
        super().__init__(SETTINGS_WIDTH, SETTINGS_HEIGHT, GLOW_BLUR, GLOW_ALPHA)
        card = _SettingsCard(tts=tts)
        card.changed.connect(self.changed)
        card.saved.connect(self.saved)
        card.tts_toggled.connect(self.tts_toggled)
        self.mount(card, GLOW_BLUR, GLOW_ALPHA)

    # -- facade kept so callers/tests talk to the window as before ----------- #
    def dismiss(self) -> None:
        self.card.dismiss()

    @property
    def _slider(self) -> QSlider:
        return self.card._slider

    @property
    def _tts_check(self) -> QCheckBox:
        return self.card._tts_check

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming) — hide, never destroy
        event.ignore()
        self.dismiss()