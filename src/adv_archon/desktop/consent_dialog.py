# mypy: ignore-errors
"""First-run consent gate for ADV ARCHON desktop (PySide6).

``show_if_needed`` is the public entry point.  It's a no-op when the user has
already accepted; otherwise it displays a modal dialog with the full legal text,
an acceptance checkbox, and Accept / Exit buttons.

Returns True when the user accepted (or already had), False when they chose to
exit (caller should call ``QApplication.quit()`` or equivalent).
"""
from __future__ import annotations

from pathlib import Path

from adv_archon.core import legal
from adv_archon.core.consent import is_consent_accepted, mark_consent_accepted


def show_if_needed(data_dir: Path, parent=None) -> bool:
    """Show consent dialog if not yet accepted.  Returns False → caller should exit."""
    if is_consent_accepted(data_dir):
        return True

    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import (
            QCheckBox,
            QDialog,
            QDialogButtonBox,
            QLabel,
            QSizePolicy,
            QTextBrowser,
            QVBoxLayout,
        )
    except ModuleNotFoundError:
        # Headless / test environment — treat as accepted.
        return True

    dlg = QDialog(parent)
    dlg.setWindowTitle("ADV ARCHON — Aviso legal y condiciones de uso")
    dlg.setMinimumSize(680, 520)
    dlg.setSizeGripEnabled(True)

    layout = QVBoxLayout(dlg)
    layout.setSpacing(12)
    layout.setContentsMargins(20, 16, 20, 16)

    # ── Header ────────────────────────────────────────────────────────────────
    header = QLabel("Aviso legal y condiciones de uso")
    font = header.font()
    font.setPointSize(14)
    font.setBold(True)
    header.setFont(font)
    layout.addWidget(header)

    sub = QLabel(
        f"ADV ARCHON · v{legal.LEGAL_VERSION} · {legal.LEGAL_LAST_UPDATED}  "
        "— Lea detenidamente antes de continuar."
    )
    sub_font = QFont(sub.font())
    sub_font.setPointSize(9)
    sub.setFont(sub_font)
    sub.setStyleSheet("color: #888;")
    layout.addWidget(sub)

    # ── Scrollable legal text ─────────────────────────────────────────────────
    browser = QTextBrowser()
    browser.setOpenExternalLinks(False)
    browser.setReadOnly(True)
    browser.setPlainText(legal.full_legal_text())
    browser.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    layout.addWidget(browser, stretch=1)

    # ── Acceptance checkbox ───────────────────────────────────────────────────
    checkbox = QCheckBox(legal.acceptance_summary())
    checkbox.setWordWrap(True)
    layout.addWidget(checkbox)

    # ── Buttons ───────────────────────────────────────────────────────────────
    btn_box = QDialogButtonBox()
    accept_btn = btn_box.addButton("Acepto y continúo", QDialogButtonBox.AcceptRole)
    btn_box.addButton("Salir", QDialogButtonBox.RejectRole)
    accept_btn.setEnabled(False)

    def _on_checkbox(state: int) -> None:
        accept_btn.setEnabled(bool(state))

    checkbox.stateChanged.connect(_on_checkbox)
    btn_box.accepted.connect(dlg.accept)
    btn_box.rejected.connect(dlg.reject)
    layout.addWidget(btn_box)

    # Force modal — must not be skipped.
    dlg.setWindowModality(Qt.ApplicationModal)

    result = dlg.exec()
    if result == QDialog.Accepted:
        mark_consent_accepted(data_dir)
        return True

    # User clicked Exit — caller must terminate.
    return False
