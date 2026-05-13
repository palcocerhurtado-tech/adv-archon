# mypy: ignore-errors
"""Design tokens for the Archon Desktop — Archon Consultancies premium UI.

Aesthetic: Marble Temple — mármol blanco como campo, obsidiana como estructura,
dorado como acento. Sidebar y TopBar en obsidiana; área principal en mármol.
"""
from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]

# ── Archon Consultancies brand palette ────────────────────────────────────────
BG           = "#050505"   # Negro Archon / Obsidiana
SURFACE      = "#111110"   # deep obsidian panel
SURFACE_UP   = "#181817"   # elevated obsidian
SURFACE_HIGH = "#2E2E2C"   # Gris piedra oscuro

BORDER       = "#2E2E2C"   # Gris piedra oscuro hairline
BORDER_MED   = "#3A3935"   # medium stone
BORDER_FOCUS = "#C9A227"   # Dorado metalizado

TEXT         = "#F7F7F4"   # Blanco mármol — text ON dark bg
TEXT_SUB     = "#B8B6AE"   # Gris piedra claro
TEXT_FAINT   = "#77746B"   # muted stone

ACCENT       = "#C9A227"   # Dorado metalizado — used sparingly
ACCENT_HOVER = "#D8B84A"
ACCENT_DIM   = "rgba(201,162,39,0.10)"
ACCENT_GLOW  = "rgba(201,162,39,0.24)"

OK           = "#5FA66D"
OK_DIM       = "rgba(95,166,109,0.12)"
WARN         = "#C9A227"
WARN_DIM     = "rgba(201,162,39,0.10)"
ERR          = "#B24A3C"
ERR_DIM      = "rgba(178,74,60,0.12)"
INFO         = "#B8B6AE"
INFO_DIM     = "rgba(184,182,174,0.10)"

# ── Marble Temple field tokens (main area — light) ────────────────────────────
MARBLE_BG     = "#F7F7F4"   # mármol blanco — main area background
MARBLE_PANEL  = "#FFFFFF"   # polished marble — cards, panels
MARBLE_WARM   = "#F0EDE6"   # warm marble — elevated card
MARBLE_BORDER = "#D8D4C8"   # hairline border on marble

OBSIDIAN      = "#050505"   # structural dark (= BG)
OBSIDIAN_MED  = "#111110"   # medium obsidian (= SURFACE)
OBSIDIAN_HIGH = "#1C1C1A"   # slightly lighter obsidian

TEXT_DARK     = "#050505"   # text ON marble
TEXT_SUB_DARK = "#3A3935"   # secondary text on marble

FONT_UI      = (
    '"Inter", "IBM Plex Sans", "Manrope", "SF Pro Text", '
    '"Segoe UI", system-ui, sans-serif'
)
FONT_DISPLAY = '"Libre Baskerville", "Georgia", serif'
FONT_SEAL    = '"Cinzel Decorative", "Libre Baskerville", "Georgia", serif'

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


def logo_full_path() -> Path:
    return PACKAGE_ROOT / "resources" / "branding" / "archon-logo-full.png"


def logo_outline_path() -> Path:
    return PACKAGE_ROOT / "resources" / "branding" / "archon-logo-outline.png"


def report_logo_path() -> Path:
    return logo_full_path()


def desktop_stylesheet() -> str:
    """Marble Temple — obsidian structure, marble field, gold accent.

    Zones:
      Sidebar / TopBar / StatusBar  → obsidian (#050505)
      Chat area / panels / dialogs  → marble white (#F7F7F4 / #FFFFFF)
      Accent / focus                → gold (#C9A227)
    """
    return f"""
* {{
    font-family: {FONT_UI};
    outline: none;
}}
/* ── Global base: marble field ───────────────────────────── */
QMainWindow, QDialog {{
    background: {MARBLE_BG};
    color: {TEXT_DARK};
}}
QWidget {{
    background: {MARBLE_BG};
    color: {TEXT_DARK};
    font-size: 13px;
}}

/* ── Obsidian structural zones ───────────────────────────── */
QFrame#Sidebar {{
    background: {OBSIDIAN};
    border-right: 1px solid {OBSIDIAN_HIGH};
}}
QFrame#TopBar {{
    background: {OBSIDIAN};
    border-bottom: 1px solid {OBSIDIAN_HIGH};
}}
QFrame#BottomBar, QStatusBar {{
    background: {OBSIDIAN};
    color: {TEXT_SUB};
    border-top: 1px solid {OBSIDIAN_HIGH};
}}

/* ── Children inside obsidian zones ─────────────────────── */
QFrame#Sidebar QWidget   {{ background: transparent; color: {TEXT}; }}
QFrame#Sidebar QLabel    {{ background: transparent; color: {TEXT}; font-size: 13px; }}
QFrame#Sidebar QLabel#Eyebrow {{
    color: {TEXT_FAINT}; font-size: 10px; font-weight: 700; letter-spacing: 0.12em;
}}
QFrame#Sidebar QLabel#AppName {{
    color: {TEXT}; font-family: {FONT_DISPLAY}; font-size: 14px; font-weight: 700;
}}
QFrame#Sidebar QLabel#Faint  {{ color: {TEXT_FAINT}; font-size: 11px; }}
QFrame#Sidebar QFrame#Divider {{
    background: {OBSIDIAN_HIGH}; max-height: 1px; min-height: 1px; border: none;
}}
QFrame#Sidebar QComboBox {{
    background: {OBSIDIAN_MED}; color: {TEXT}; border: 1px solid {SURFACE_HIGH};
    border-radius: 8px; padding: 4px 10px; font-size: 12px; min-height: 26px;
}}
QFrame#Sidebar QComboBox:hover {{ border-color: {ACCENT}; }}
QFrame#Sidebar QComboBox::drop-down {{ border: none; width: 18px; }}
QFrame#Sidebar QComboBox QAbstractItemView {{
    background: {SURFACE_HIGH}; border: 1px solid {BORDER_MED};
    border-radius: 8px; color: {TEXT}; padding: 4px;
    selection-background-color: {ACCENT_DIM};
}}
QFrame#TopBar QLabel {{ background: transparent; color: {TEXT_FAINT}; font-size: 12px; }}
QStatusBar QLabel     {{ background: transparent; color: {TEXT_SUB}; }}

/* ── Marble panels ───────────────────────────────────────── */
QFrame#Panel {{
    background: {MARBLE_PANEL};
    border: 1px solid {MARBLE_BORDER};
    border-radius: 14px;
}}
QFrame#Card {{
    background: {MARBLE_WARM};
    border: 1px solid {MARBLE_BORDER};
    border-radius: 10px;
}}
QFrame#Composer {{
    background: {MARBLE_PANEL};
    border: 1px solid {MARBLE_BORDER};
    border-radius: 16px;
}}
QFrame#ComposerFocused {{
    background: {MARBLE_PANEL};
    border: 2px solid {ACCENT};
    border-radius: 16px;
}}

/* ── Message bubbles ─────────────────────────────────────── */
QFrame#MsgUser {{
    background: {MARBLE_PANEL};
    border: 1px solid {MARBLE_BORDER};
    border-radius: 12px;
    border-bottom-right-radius: 4px;
}}
QFrame#MsgAssistant {{
    background: transparent;
    border: none;
}}

/* ── Tool / status badges ────────────────────────────────── */
QFrame#ToolBadge {{
    background: {ACCENT_DIM};
    border: 1px solid {ACCENT_GLOW};
    border-radius: 6px;
}}
QFrame#OkBadge  {{
    background: {OK_DIM};  border: 1px solid rgba(95,166,109,0.25); border-radius: 6px;
}}
QFrame#WarnBadge {{
    background: {WARN_DIM}; border: 1px solid rgba(201,162,39,0.25); border-radius: 6px;
}}
QFrame#ErrBadge {{
    background: {ERR_DIM}; border: 1px solid rgba(178,74,60,0.25); border-radius: 6px;
}}
QFrame#InfoBadge {{
    background: {INFO_DIM}; border: 1px solid rgba(184,182,174,0.20); border-radius: 6px;
}}
QFrame#Divider  {{ background: {MARBLE_BORDER}; max-height: 1px; min-height: 1px; border: none; }}
QFrame#DropZone {{ background: {ACCENT_DIM}; border: 1px dashed {ACCENT}; border-radius: 12px; }}

/* ── Labels (marble context) ─────────────────────────────── */
QLabel {{ color: {TEXT_DARK}; background: transparent; font-size: 13px; }}
QLabel#Sub     {{ color: {TEXT_SUB_DARK}; font-size: 12px; }}
QLabel#Faint   {{ color: {TEXT_FAINT};    font-size: 11px; }}
QLabel#Accent  {{ color: {ACCENT};        font-size: 12px; font-weight: 600; }}
QLabel#Ok      {{ color: {OK};            font-size: 12px; font-weight: 600; }}
QLabel#Warn    {{ color: {WARN};          font-size: 12px; font-weight: 600; }}
QLabel#Err     {{ color: {ERR};           font-size: 12px; font-weight: 600; }}
QLabel#AppName {{
    color: {TEXT_DARK}; font-family: {FONT_DISPLAY}; font-size: 14px; font-weight: 700;
}}
QLabel#Eyebrow {{
    color: {TEXT_FAINT}; font-family: {FONT_UI}; font-size: 10px; font-weight: 700;
    letter-spacing: 0.12em; text-transform: uppercase;
}}
QLabel#RoleTag {{
    color: {ACCENT}; font-family: {FONT_SEAL}; font-size: 10px; font-weight: 700;
    letter-spacing: 0.08em;
}}
QLabel#RoleTagUser {{
    color: {TEXT_FAINT}; font-size: 10px; font-weight: 600; letter-spacing: 0.08em;
}}
QLabel#Timestamp {{ color: {TEXT_FAINT}; font-size: 10px; }}

/* ── Inputs (marble context) ─────────────────────────────── */
QPlainTextEdit, QTextEdit {{
    background: transparent;
    color: {TEXT_DARK};
    border: none;
    font-size: 13px;
    line-height: 1.65;
    selection-background-color: {ACCENT_DIM};
    selection-color: {TEXT_DARK};
}}
QTextEdit[readOnly="true"] {{
    background: transparent; border: none; color: {TEXT_DARK};
    font-size: 13px; line-height: 1.65;
    selection-background-color: {ACCENT_DIM};
}}
QPlainTextEdit {{
    color: {TEXT_SUB_DARK}; font-size: 12px;
}}

/* ── Buttons ─────────────────────────────────────────────── */
QPushButton {{
    background: {MARBLE_PANEL};
    color: {TEXT_DARK};
    border: 1px solid {MARBLE_BORDER};
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
    min-height: 28px;
}}
QPushButton:hover {{
    background: {MARBLE_WARM};
    border-color: {ACCENT};
}}
QPushButton:pressed {{ background: {MARBLE_BORDER}; }}
QPushButton:disabled {{
    color: {TEXT_FAINT}; background: {MARBLE_WARM}; border-color: {MARBLE_BORDER};
}}
QPushButton#Primary {{
    background: {ACCENT};
    color: {OBSIDIAN};
    border: none;
    border-radius: 8px;
    padding: 7px 18px;
    font-weight: 700;
    min-height: 32px;
}}
QPushButton#Primary:hover {{ background: {ACCENT_HOVER}; color: {OBSIDIAN}; }}
QPushButton#Primary:disabled {{ background: {MARBLE_WARM}; color: {TEXT_FAINT}; border: none; }}
QPushButton#Ghost {{
    background: transparent;
    border: none;
    color: {TEXT_SUB_DARK};
    padding: 5px 10px;
    border-radius: 8px;
}}
QPushButton#Ghost:hover {{ color: {TEXT_DARK}; background: {MARBLE_WARM}; }}

/* ── Nav buttons (live inside obsidian sidebar) ──────────── */
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
QPushButton#NavBtn:hover {{ color: {TEXT}; background: {OBSIDIAN_HIGH}; }}
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
QPushButton#NavBtnGold {{
    background: {ACCENT};
    border: 1px solid {ACCENT_HOVER};
    color: {OBSIDIAN};
    text-align: left;
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 800;
    min-height: 36px;
}}
QPushButton#NavBtnGold:hover {{ background: {ACCENT_HOVER}; color: {OBSIDIAN}; }}
QFrame#StudioHero {{
    background: {MARBLE_PANEL};
    border: 1px solid {ACCENT};
    border-radius: 14px;
}}
QFrame#StudioCard {{
    background: {MARBLE_WARM};
    border: 1px solid {MARBLE_BORDER};
    border-radius: 12px;
}}
QFrame#StudioCard:hover {{
    border: 1px solid {ACCENT};
    background: {MARBLE_PANEL};
}}
QFrame#StudioMetric {{
    background: {MARBLE_PANEL};
    border: 1px solid {MARBLE_BORDER};
    border-radius: 8px;
}}
QLabel#StudioTitle {{
    color: {TEXT_DARK};
    font-family: {FONT_DISPLAY};
    font-size: 22px;
    font-weight: 700;
}}
QLabel#StudioCase {{
    color: {TEXT_DARK};
    font-family: {FONT_DISPLAY};
    font-size: 15px;
    font-weight: 700;
}}
QLabel#StudioDecision {{
    color: {ACCENT};
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.08em;
}}
QPushButton#IconBtn {{
    background: transparent;
    border: none;
    color: {TEXT_SUB_DARK};
    padding: 6px;
    border-radius: 8px;
    min-width: 28px;
    min-height: 28px;
    font-size: 16px;
}}
QPushButton#IconBtn:hover {{ color: {TEXT_DARK}; background: {MARBLE_WARM}; }}

/* ── Scrollbars ──────────────────────────────────────────── */
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 5px; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: {MARBLE_BORDER}; min-height: 24px; border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{ background: {TEXT_FAINT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar:horizontal {{ height: 0px; }}

/* ── Splitter ────────────────────────────────────────────── */
QSplitter::handle:horizontal {{ background: {MARBLE_BORDER}; width: 1px; }}
QSplitter::handle:vertical   {{ background: {MARBLE_BORDER}; height: 1px; }}

/* ── Progress bar (streaming indicator) ──────────────────── */
QProgressBar {{
    background: {MARBLE_BORDER}; border: none; border-radius: 1px; max-height: 2px;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 1px; }}

/* ── ComboBox (marble context) ───────────────────────────── */
QComboBox {{
    background: {MARBLE_PANEL}; color: {TEXT_DARK}; border: 1px solid {MARBLE_BORDER};
    border-radius: 8px; padding: 4px 10px; font-size: 12px; min-height: 26px;
}}
QComboBox:hover {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background: {MARBLE_PANEL}; border: 1px solid {MARBLE_BORDER};
    border-radius: 8px; color: {TEXT_DARK}; padding: 4px;
    selection-background-color: {ACCENT_DIM}; selection-color: {TEXT_DARK};
}}

/* ── ListWidget ──────────────────────────────────────────── */
QListWidget {{
    background: transparent; border: none; color: {TEXT_SUB_DARK};
    font-size: 12px; outline: none;
}}
QListWidget::item {{ padding: 4px 6px; border-radius: 6px; }}
QListWidget::item:selected {{ background: {ACCENT_DIM}; color: {ACCENT}; }}
QListWidget::item:hover     {{ background: {MARBLE_WARM}; }}

/* ── Menu bar ────────────────────────────────────────────── */
QMenuBar {{
    background: {OBSIDIAN}; color: {TEXT_SUB};
    border-bottom: 1px solid {OBSIDIAN_HIGH}; font-size: 12px;
}}
QMenuBar::item:selected {{ background: {OBSIDIAN_HIGH}; color: {TEXT}; }}
QMenu {{
    background: {MARBLE_PANEL}; border: 1px solid {MARBLE_BORDER};
    border-radius: 8px; color: {TEXT_DARK}; padding: 4px;
}}
QMenu::item {{ padding: 6px 20px; border-radius: 6px; }}
QMenu::item:selected {{ background: {ACCENT_DIM}; color: {ACCENT}; }}
"""


__all__ = [
    "ACCENT", "ACCENT_DIM", "ACCENT_GLOW", "ACCENT_HOVER",
    "BG", "BORDER", "BORDER_FOCUS", "BORDER_MED",
    "ERR", "ERR_DIM", "INFO", "INFO_DIM",
    "FONT_DISPLAY", "FONT_SEAL", "FONT_UI",
    "MARBLE_BG", "MARBLE_BORDER", "MARBLE_PANEL", "MARBLE_WARM",
    "OBSIDIAN", "OBSIDIAN_HIGH", "OBSIDIAN_MED",
    "OK", "OK_DIM", "SURFACE", "SURFACE_HIGH", "SURFACE_UP",
    "TEXT", "TEXT_DARK", "TEXT_FAINT", "TEXT_SUB", "TEXT_SUB_DARK", "WARN", "WARN_DIM",
    "GRAPHITE", "MATTE_BLACK", "MUTED_TEXT", "NEON_GREEN",
    "NEON_PINK", "SOFT_GRAPHITE", "WHITE",
    "desktop_stylesheet", "logo_full_path", "logo_outline_path", "logo_path",
    "report_logo_path",
]
