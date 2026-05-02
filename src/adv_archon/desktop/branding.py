# mypy: ignore-errors
"""Design tokens for the Archon Desktop — architect-grade premium dark UI."""
from __future__ import annotations

from pathlib import Path

from adv_archon.core.config import PACKAGE_ROOT

# ── Color system ──────────────────────────────────────────────────────────────
BG           = "#09090B"   # zinc-950 — absolute dark
SURFACE      = "#111113"   # cards / panels
SURFACE_UP   = "#18181C"   # elevated elements
SURFACE_HIGH = "#1F1F24"   # tooltips, popovers

BORDER       = "#242429"   # hairline border
BORDER_MED   = "#2E2E36"   # medium weight
BORDER_FOCUS = "#3B6FFF"   # input focus ring

TEXT         = "#F4F4F6"   # primary text
TEXT_SUB     = "#9F9FAA"   # secondary / muted
TEXT_FAINT   = "#52525C"   # placeholder, disabled

ACCENT       = "#3B6FFF"   # Blueprint Blue — architect's drawing colour
ACCENT_HOVER = "#5585FF"
ACCENT_DIM   = "rgba(59,111,255,0.10)"
ACCENT_GLOW  = "rgba(59,111,255,0.22)"

OK           = "#22C55E"
OK_DIM       = "rgba(34,197,94,0.10)"
WARN         = "#F59E0B"
WARN_DIM     = "rgba(245,158,11,0.10)"
ERR          = "#EF4444"
ERR_DIM      = "rgba(239,68,68,0.10)"
INFO         = "#8B5CF6"
INFO_DIM     = "rgba(139,92,246,0.10)"

# ── Backwards compat aliases ──────────────────────────────────────────────────
MATTE_BLACK  = BG
WHITE        = TEXT
NEON_GREEN   = OK
GRAPHITE     = SURFACE
NEON_PINK    = INFO
SOFT_GRAPHITE = BORDER_MED
MUTED_TEXT   = TEXT_SUB


def logo_path() -> Path:
    return PACKAGE_ROOT / "resources" / "branding" / "archon-logo.png"


def desktop_stylesheet() -> str:
    return f"""
* {{
    font-family: "Inter", "SF Pro Text", "Segoe UI", system-ui, sans-serif;
    outline: none;
}}
QMainWindow, QDialog {{
    background: {BG};
    color: {TEXT};
}}
QWidget {{
    background: {BG};
    color: {TEXT};
    font-size: 13px;
}}
/* Panels */
QFrame#Sidebar {{
    background: {SURFACE};
    border-right: 1px solid {BORDER};
}}
QFrame#TopBar {{
    background: {SURFACE};
    border-bottom: 1px solid {BORDER};
}}
QFrame#BottomBar {{
    background: {SURFACE};
    border-top: 1px solid {BORDER};
}}
QFrame#Panel {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QFrame#Card {{
    background: {SURFACE_UP};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QFrame#Composer {{
    background: {SURFACE_UP};
    border: 1px solid {BORDER_MED};
    border-radius: 16px;
}}
QFrame#ComposerFocused {{
    background: {SURFACE_UP};
    border: 1px solid {BORDER_FOCUS};
    border-radius: 16px;
}}
QFrame#MsgUser {{
    background: {SURFACE_UP};
    border: 1px solid {BORDER};
    border-radius: 12px;
    border-bottom-right-radius: 4px;
}}
QFrame#MsgAssistant {{
    background: transparent;
    border: none;
}}
QFrame#ToolBadge {{
    background: {ACCENT_DIM};
    border: 1px solid {ACCENT_GLOW};
    border-radius: 6px;
}}
QFrame#OkBadge    {{ background: {OK_DIM};   border: 1px solid rgba(34,197,94,0.25);  border-radius: 6px; }}
QFrame#WarnBadge  {{ background: {WARN_DIM}; border: 1px solid rgba(245,158,11,0.25); border-radius: 6px; }}
QFrame#ErrBadge   {{ background: {ERR_DIM};  border: 1px solid rgba(239,68,68,0.25);  border-radius: 6px; }}
QFrame#InfoBadge  {{ background: {INFO_DIM}; border: 1px solid rgba(139,92,246,0.25); border-radius: 6px; }}
QFrame#Divider    {{ background: {BORDER};   max-height: 1px; min-height: 1px; border: none; }}
QFrame#DropZone   {{
    background: {ACCENT_DIM};
    border: 1px dashed {ACCENT};
    border-radius: 12px;
}}
/* Labels */
QLabel {{ color: {TEXT}; background: transparent; font-size: 13px; }}
QLabel#Sub     {{ color: {TEXT_SUB};   font-size: 12px; }}
QLabel#Faint   {{ color: {TEXT_FAINT}; font-size: 11px; }}
QLabel#Accent  {{ color: {ACCENT};     font-size: 12px; font-weight: 600; }}
QLabel#Ok      {{ color: {OK};         font-size: 12px; font-weight: 600; }}
QLabel#Warn    {{ color: {WARN};       font-size: 12px; font-weight: 600; }}
QLabel#Err     {{ color: {ERR};        font-size: 12px; font-weight: 600; }}
QLabel#AppName {{ color: {TEXT}; font-size: 13px; font-weight: 700; letter-spacing: 0.02em; }}
QLabel#Eyebrow {{
    color: {TEXT_FAINT};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.12em;
}}
QLabel#RoleTag {{
    color: {ACCENT};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
}}
QLabel#RoleTagUser {{
    color: {TEXT_FAINT};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.08em;
}}
QLabel#Timestamp {{
    color: {TEXT_FAINT};
    font-size: 10px;
}}
/* Inputs */
QPlainTextEdit, QTextEdit {{
    background: transparent;
    color: {TEXT};
    border: none;
    font-size: 13px;
    line-height: 1.65;
    selection-background-color: {ACCENT_DIM};
    selection-color: {TEXT};
}}
/* Buttons */
QPushButton {{
    background: {SURFACE_UP};
    color: {TEXT};
    border: 1px solid {BORDER_MED};
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
    min-height: 28px;
}}
QPushButton:hover {{
    background: {SURFACE_HIGH};
    border-color: {BORDER_FOCUS};
}}
QPushButton:pressed {{ background: {SURFACE}; }}
QPushButton:disabled {{ color: {TEXT_FAINT}; background: {SURFACE}; border-color: {BORDER}; }}
QPushButton#Primary {{
    background: {ACCENT};
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 7px 18px;
    font-weight: 700;
    min-height: 32px;
}}
QPushButton#Primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#Primary:disabled {{ background: {SURFACE_UP}; color: {TEXT_FAINT}; }}
QPushButton#Ghost {{
    background: transparent;
    border: none;
    color: {TEXT_SUB};
    padding: 5px 10px;
    border-radius: 8px;
}}
QPushButton#Ghost:hover {{ color: {TEXT}; background: {SURFACE_UP}; }}
QPushButton#NavBtn {{
    background: transparent;
    border: none;
    color: {TEXT_SUB};
    text-align: left;
    padding: 7px 12px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    min-height: 34px;
}}
QPushButton#NavBtn:hover {{ color: {TEXT}; background: {SURFACE_UP}; }}
QPushButton#NavBtnActive {{
    background: {ACCENT_DIM};
    border: 1px solid {ACCENT_GLOW};
    color: {ACCENT};
    text-align: left;
    padding: 7px 12px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 700;
    min-height: 34px;
}}
QPushButton#IconBtn {{
    background: transparent;
    border: none;
    color: {TEXT_SUB};
    padding: 6px;
    border-radius: 8px;
    min-width: 28px;
    min-height: 28px;
    font-size: 16px;
}}
QPushButton#IconBtn:hover {{ color: {TEXT}; background: {SURFACE_UP}; }}
/* Scrollbars */
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{
    background: transparent; width: 5px; margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_MED}; min-height: 24px; border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{ background: {TEXT_FAINT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar:horizontal {{ height: 0px; }}
/* Splitter */
QSplitter::handle:horizontal {{ background: {BORDER}; width: 1px; }}
QSplitter::handle:vertical   {{ background: {BORDER}; height: 1px; }}
/* Progress (used as streaming indicator) */
QProgressBar {{
    background: {BORDER}; border: none; border-radius: 1px; max-height: 2px;
}}
QProgressBar::chunk {{
    background: {ACCENT}; border-radius: 1px;
}}
/* ComboBox */
QComboBox {{
    background: {SURFACE_UP}; color: {TEXT}; border: 1px solid {BORDER_MED};
    border-radius: 8px; padding: 4px 10px; font-size: 12px; min-height: 26px;
}}
QComboBox:hover {{ border-color: {BORDER_FOCUS}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE_HIGH}; border: 1px solid {BORDER_MED};
    border-radius: 8px; color: {TEXT}; padding: 4px;
    selection-background-color: {ACCENT_DIM};
}}
/* ListWidget — historial, adjuntos recientes */
QListWidget {{
    background: transparent; border: none; color: {TEXT_SUB};
    font-size: 12px; outline: none;
}}
QListWidget::item {{
    padding: 4px 6px; border-radius: 6px;
}}
QListWidget::item:selected {{
    background: {ACCENT_DIM}; color: {ACCENT};
}}
QListWidget::item:hover {{
    background: {SURFACE_UP};
}}
/* PlainTextEdit inside panels — read-only context/sources views */
QPlainTextEdit {{
    background: transparent; color: {TEXT_SUB}; border: none;
    font-size: 12px; line-height: 1.55;
    selection-background-color: {ACCENT_DIM};
    selection-color: {TEXT};
}}
/* AutoTextEdit inside message bubbles (read-only QTextEdit) */
QTextEdit[readOnly="true"] {{
    background: transparent; border: none; color: {TEXT};
    font-size: 13px; line-height: 1.65;
    selection-background-color: {ACCENT_DIM};
    selection-color: {TEXT};
}}
/* Menu bar */
QMenuBar {{
    background: {SURFACE}; color: {TEXT_SUB};
    border-bottom: 1px solid {BORDER}; font-size: 12px;
}}
QMenuBar::item:selected {{ background: {SURFACE_UP}; color: {TEXT}; }}
QMenu {{
    background: {SURFACE_HIGH}; border: 1px solid {BORDER_MED};
    border-radius: 8px; color: {TEXT}; padding: 4px;
}}
QMenu::item {{ padding: 6px 20px; border-radius: 6px; }}
QMenu::item:selected {{ background: {ACCENT_DIM}; color: {ACCENT}; }}
"""


__all__ = [
    "ACCENT", "ACCENT_DIM", "ACCENT_GLOW", "ACCENT_HOVER",
    "BG", "BORDER", "BORDER_FOCUS", "BORDER_MED",
    "ERR", "ERR_DIM", "INFO", "INFO_DIM",
    "OK", "OK_DIM", "SURFACE", "SURFACE_HIGH", "SURFACE_UP",
    "TEXT", "TEXT_FAINT", "TEXT_SUB", "WARN", "WARN_DIM",
    "GRAPHITE", "MATTE_BLACK", "MUTED_TEXT", "NEON_GREEN",
    "NEON_PINK", "SOFT_GRAPHITE", "WHITE",
    "desktop_stylesheet", "logo_path",
]
