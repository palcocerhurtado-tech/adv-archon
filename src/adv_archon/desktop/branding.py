from __future__ import annotations

from pathlib import Path

from adv_archon.core.config import PACKAGE_ROOT

MATTE_BLACK = "#0B0C0E"
WHITE = "#F6F7FB"
NEON_GREEN = "#78FF6B"
GRAPHITE = "#1C1F24"
NEON_PINK = "#FF4FD8"
SOFT_GRAPHITE = "#2A2E34"
MUTED_TEXT = "#B9C0CB"


def logo_path() -> Path:
    return PACKAGE_ROOT / "resources" / "branding" / "archon-logo.png"


def desktop_stylesheet() -> str:
    return f"""
    QWidget#Root {{
        background: {MATTE_BLACK};
        color: {WHITE};
    }}
    QScrollArea#RootScroll {{
        border: none;
        background: {MATTE_BLACK};
    }}
    QMainWindow {{
        background: {MATTE_BLACK};
    }}
    QMenuBar {{
        background: {MATTE_BLACK};
        color: {WHITE};
        border-bottom: 1px solid {SOFT_GRAPHITE};
        padding: 4px 8px;
    }}
    QMenuBar::item:selected {{
        background: {GRAPHITE};
        border-radius: 8px;
    }}
    QFrame#HeroCard,
    QFrame#PanelCard,
    QFrame#ComposerCard,
    QFrame#SidebarCard,
    QFrame#AttachmentsCard,
    QFrame#TranscriptCard,
    QFrame#OnboardingCard,
    QFrame#OnboardingPromptCard {{
        background: {GRAPHITE};
        border: 1px solid {SOFT_GRAPHITE};
        border-radius: 22px;
    }}
    QFrame#OnboardingPromptCard {{
        background: #171A1F;
        border-radius: 18px;
    }}
    QLabel#HeroEyebrow {{
        color: {NEON_GREEN};
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }}
    QLabel#HeroTitle {{
        color: {WHITE};
        font-size: 30px;
        font-weight: 800;
    }}
    QLabel#HeroSubtitle {{
        color: {MUTED_TEXT};
        font-size: 14px;
        line-height: 1.35em;
    }}
    QLabel#SectionTitle {{
        color: {WHITE};
        font-size: 14px;
        font-weight: 700;
        padding-bottom: 2px;
    }}
    QLabel#OnboardingTitle {{
        color: {WHITE};
        font-size: 24px;
        font-weight: 800;
    }}
    QLabel#OnboardingBody {{
        color: {MUTED_TEXT};
        font-size: 14px;
        line-height: 1.4em;
    }}
    QLabel#StatusPill {{
        background: rgba(120, 255, 107, 0.12);
        color: {NEON_GREEN};
        border: 1px solid rgba(120, 255, 107, 0.55);
        border-radius: 14px;
        padding: 7px 12px;
        font-weight: 700;
    }}
    QLabel#MetaLabel {{
        color: {MUTED_TEXT};
        font-size: 12px;
        font-weight: 600;
    }}
    QComboBox,
    QTextEdit,
    QPlainTextEdit,
    QListWidget {{
        background: #111316;
        color: {WHITE};
        border: 1px solid {SOFT_GRAPHITE};
        border-radius: 16px;
        padding: 10px 12px;
        selection-background-color: {NEON_PINK};
        selection-color: {MATTE_BLACK};
    }}
    QComboBox {{
        min-height: 38px;
        padding-right: 28px;
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QPlainTextEdit#Transcript {{
        background: #0F1012;
        border: 1px solid {SOFT_GRAPHITE};
        border-left: 3px solid {NEON_GREEN};
        border-radius: 18px;
        padding: 16px;
    }}
    QPlainTextEdit#SidebarPanel {{
        background: #13161A;
        border: 1px solid {SOFT_GRAPHITE};
        border-radius: 18px;
        padding: 14px;
    }}
    QTextEdit#PromptInput {{
        background: #0F1012;
        border: 1px solid {SOFT_GRAPHITE};
        border-radius: 18px;
        padding: 14px;
    }}
    QListWidget#CompactList {{
        background: #13161A;
        border: 1px solid {SOFT_GRAPHITE};
        border-radius: 18px;
        padding: 8px;
    }}
    QListWidget#AttachmentList {{
        background: #101215;
        border: 1px solid {SOFT_GRAPHITE};
        border-radius: 18px;
        padding: 8px;
    }}
    QListWidget::item {{
        border-radius: 12px;
        padding: 8px 10px;
        margin: 2px 0;
    }}
    QListWidget::item:selected {{
        background: rgba(255, 79, 216, 0.18);
        border: 1px solid rgba(255, 79, 216, 0.55);
    }}
    QPushButton {{
        background: #181B20;
        color: {WHITE};
        border: 1px solid {SOFT_GRAPHITE};
        border-radius: 14px;
        padding: 10px 14px;
        font-weight: 700;
    }}
    QPushButton:hover {{
        border-color: {NEON_GREEN};
    }}
    QPushButton:disabled {{
        color: #6B727C;
        background: #111316;
        border-color: #20242A;
    }}
    QPushButton#PrimaryButton {{
        background: {NEON_GREEN};
        color: {MATTE_BLACK};
        border: 1px solid rgba(120, 255, 107, 0.85);
    }}
    QPushButton#PrimaryButton:hover {{
        background: #94FF8C;
    }}
    QPushButton#AccentButton {{
        background: {NEON_PINK};
        color: {MATTE_BLACK};
        border: 1px solid rgba(255, 79, 216, 0.8);
    }}
    QPushButton#AccentButton:hover {{
        background: #FF7BE3;
    }}
    QPushButton#GhostButton {{
        background: transparent;
        border: 1px solid {SOFT_GRAPHITE};
        color: {MUTED_TEXT};
    }}
    QPushButton#GhostButton:hover {{
        color: {WHITE};
        border-color: {NEON_PINK};
    }}
    QPushButton#QuickPromptButton {{
        background: transparent;
        border: 1px solid rgba(120, 255, 107, 0.3);
        color: {WHITE};
    }}
    QPushButton#QuickPromptButton:hover {{
        border-color: {NEON_GREEN};
        background: rgba(120, 255, 107, 0.08);
    }}
    QProgressBar {{
        background: #121417;
        color: {WHITE};
        border: 1px solid {SOFT_GRAPHITE};
        border-radius: 10px;
        padding: 2px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background: {NEON_GREEN};
        border-radius: 8px;
    }}
    QSplitter::handle {{
        background: {SOFT_GRAPHITE};
        width: 2px;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 12px;
        margin: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: #4B525C;
        min-height: 24px;
        border-radius: 6px;
    }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    """


__all__ = [
    "GRAPHITE",
    "MATTE_BLACK",
    "MUTED_TEXT",
    "NEON_GREEN",
    "NEON_PINK",
    "SOFT_GRAPHITE",
    "WHITE",
    "desktop_stylesheet",
    "logo_path",
]
