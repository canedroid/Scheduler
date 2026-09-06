"""Theme helpers for the Solo Leveling HUD: dark glass, purple glow, HUD fonts."""
from __future__ import annotations

from PyQt6.QtGui import QColor, QFont, QFontDatabase
from PyQt6.QtWidgets import QGraphicsDropShadowEffect

from scheduler import config


def qcolor(hex_value: str, alpha: int = 255) -> QColor:
    color = QColor(hex_value)
    color.setAlpha(alpha)
    return color


PURPLE = qcolor(config.PURPLE)
PURPLE_SOFT = qcolor(config.PURPLE_SOFT)
PURPLE_GLOW = qcolor(config.PURPLE_GLOW)
TEXT = qcolor(config.TEXT)
TEXT_DIM = qcolor(config.TEXT_DIM)
DANGER = qcolor(config.DANGER)
SUCCESS = qcolor(config.SUCCESS)
WARNING = qcolor(config.WARNING)
GLASS = qcolor(config.BG_GLASS)
GLASS_STRONG = qcolor(config.BG_GLASS_STRONG)


def header_font(pixel_size: int = 15, bold: bool = True) -> QFont:
    font = QFont(config.FONT_FAMILY_HEADER, pixel_size)
    font.setPixelSize(pixel_size)
    font.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    return font


def body_font(pixel_size: int = 12, bold: bool = False) -> QFont:
    font = QFont(config.FONT_FAMILY, pixel_size)
    font.setPixelSize(pixel_size)
    font.setWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
    return font


def glow(widget, color: str = config.PURPLE, blur: int = 42, alpha: int = 220, offset: int = 0):
    """Glowing outer shadow used on every frameless window."""
    effect = QGraphicsDropShadowEffect(widget)
    glow_color = QColor(color)
    glow_color.setAlpha(alpha)
    effect.setColor(glow_color)
    effect.setBlurRadius(blur)
    effect.setOffset(offset, offset)
    return effect


def button_qss(outline: str, hover: str, text: str = config.TEXT, padding: str = "8px 16px") -> str:
    return f"""
    QPushButton {{
        color: {text};
        background-color: rgba(18, 12, 28, 90);
        border: 1px solid {outline};
        border-radius: 9px;
        padding: {padding};
        font-family: "{config.FONT_FAMILY_HEADER}";
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 1px;
    }}
    QPushButton:hover {{
        background-color: {hover};
        border-color: {config.PURPLE_GLOW};
    }}
    QPushButton:pressed {{
        background-color: rgba(155, 81, 224, 60);
    }}
    """


def scrollbar_qss() -> str:
    return f"""
    QListWidget {{
        background: transparent;
        border: 1px solid rgba(155, 81, 224, 90);
        border-radius: 10px;
        outline: none;
    }}
    QListWidget::item {{
        color: {config.TEXT};
        border-bottom: 1px solid rgba(155, 81, 224, 40);
        padding: 8px;
    }}
    QListWidget::item:selected {{
        background-color: rgba(155, 81, 224, 70);
        color: {config.TEXT};
    }}
    QScrollBar:vertical {{
        background: rgba(18, 12, 28, 120);
        width: 8px;
        margin: 4px 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {config.PURPLE};
        min-height: 24px;
        border-radius: 4px;
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    """


def font_families() -> tuple[str, str]:
    available = set(QFontDatabase.families())
    header = config.FONT_FAMILY_HEADER if config.FONT_FAMILY_HEADER in available else "Segoe UI"
    body = config.FONT_FAMILY if config.FONT_FAMILY in available else "Calibri"
    return header, body