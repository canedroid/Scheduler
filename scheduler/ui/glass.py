"""Glass-shell wrapper: keeps the soft halo while avoiding the Windows layered bug.

On Windows, a ``QGraphicsDropShadowEffect`` applied to a translucent top-level
window pads that window's layered update rectangle into negative coordinates,
which the OS rejects with ``UpdateLayeredWindowIndirect failed ...`` and leaves
white unpainted regions. Every frameless app window is therefore a thin
``GlassShell`` (top-level, translucent, opacity-bound) that mounts its content
as a child "card"; the card carries the drop shadow, so the halo renders
*inside* the window's own bounds and Windows never sees an invalid update rect.
"""
from __future__ import annotations

from PyQt6.QtCore import QEvent, QPoint, Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSlider,
    QAbstractSpinBox,
    QComboBox,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from scheduler import config
from scheduler.ui import theme

_DRAG_PROPAGATING = (
    QAbstractButton,      # push buttons, checkboxes, tool buttons
    QAbstractSlider,      # sliders
    QAbstractSpinBox,     # time/date/spin edits
    QComboBox,
    QAbstractItemView,    # list/table/tree views
    QLineEdit,
    QTextEdit,
    QPlainTextEdit,
)


def _is_drag_target(widget: QWidget | None) -> bool:
    """True when a press on ``widget`` should begin a window drag.

    Interactive controls propagate the event to themselves; everything else
    (labels, headers, blank card space) is a drag handle for the frameless shell.
    """
    return widget is not None and not isinstance(widget, _DRAG_PROPAGATING)


def halo_for(blur: int) -> int:
    """Transparent margin (px) a card needs so its full glow fits in the window."""
    return blur + 12


class GlassShell(QWidget):
    """Frameless translucent window sized = ``content + halo margin`` on each side.

    Subclasses build a content card and call :meth:`mount`; ``show_centered`` and
    Esc-to-hide live here, but the drop shadow never does — it belongs to the
    card (see module docstring).
    """

    def __init__(self, content_w: int, content_h: int, blur: int, alpha: int):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool,
        )
        self._margin = halo_for(blur)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(content_w + 2 * self._margin, content_h + 2 * self._margin)
        theme.bind_opacity(self)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(self._margin, self._margin, self._margin, self._margin)
        self._mounted: QWidget | None = None

    def mount(self, card: QWidget, blur: int, alpha: int, draggable: bool = True) -> None:
        """Add ``card`` centered and apply the glow to the card (never the shell).

        ``draggable`` turns the card's non-interactive space into a native drag
        handle. Popups opt out so their click-anywhere-to-dismiss still works.
        """
        card.setGraphicsEffect(theme.glow(card, config.PURPLE, blur=blur, alpha=alpha))
        self._layout.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
        self._mounted = card
        if draggable:
            card.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (Qt naming)
        """Start a native OS drag when the user presses non-interactive card space."""
        if (
            event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            hit = self._mounted.childAt(event.position().toPoint())
            if _is_drag_target(hit):
                self._begin_system_move()
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def _begin_system_move(self) -> None:
        handle = self.window().windowHandle()
        if handle is not None:
            handle.startSystemMove()

    @property
    def card(self) -> QWidget:
        return self._mounted

    def show_centered(self) -> None:
        screen = QGuiApplication.primaryScreen()
        geo = screen.availableGeometry() if screen else self.geometry()
        self.move(QPoint(geo.center().x() - self.width() // 2, geo.center().y() - self.height() // 2))
        self.show()
        self.raise_()

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)