# mypy: ignore-errors
"""Dashboard visual de expedientes — tarjetas de estado, métricas y acceso rápido."""

from __future__ import annotations

from importlib.util import find_spec
from typing import Any

from adv_archon.desktop.branding import (
    ACCENT,
    ERR,
    MARBLE_BG,
    MARBLE_BORDER,
    MARBLE_PANEL,
    MARBLE_WARM,
    OK,
    TEXT_FAINT,
    TEXT_SUB,
    WARN,
)

PYSIDE6_AVAILABLE = find_spec("PySide6") is not None

Qt: Any = None
QFrame: Any = None
QGridLayout: Any = None
QHBoxLayout: Any = None
QLabel: Any = None
QPushButton: Any = None
QScrollArea: Any = None
QSizePolicy: Any = None
QVBoxLayout: Any = None
QWidget: Any = None
Signal: Any = None

if PYSIDE6_AVAILABLE:
    from importlib import import_module
    _c = import_module("PySide6.QtCore")
    _w = import_module("PySide6.QtWidgets")
    Qt = _c.Qt
    Signal = _c.Signal
    QFrame = _w.QFrame
    QGridLayout = _w.QGridLayout
    QHBoxLayout = _w.QHBoxLayout
    QLabel = _w.QLabel
    QPushButton = _w.QPushButton
    QScrollArea = _w.QScrollArea
    QSizePolicy = _w.QSizePolicy
    QVBoxLayout = _w.QVBoxLayout
    QWidget = _w.QWidget


# ── Status metadata ───────────────────────────────────────────────────────────

_STATUS_COLOUR = {
    "borrador":          TEXT_FAINT,
    "geocodificando":    ACCENT,
    "geocodificado":     OK,
    "analizando":        ACCENT,
    "analizado":         ACCENT,
    "informe_generado":  OK,
    "informe_listo":     OK,
    "requiere_revision": WARN,
    "error":             ERR,
}

_STATUS_LABEL = {
    "borrador":          "Borrador",
    "geocodificando":    "Geocodificando…",
    "geocodificado":     "Ubicación resuelta",
    "analizando":        "Analizando…",
    "analizado":         "Analizado",
    "informe_generado":  "Informe generado",
    "informe_listo":     "Informe listo",
    "requiere_revision": "Requiere revisión",
    "error":             "Error",
}

_STATUS_GROUPS = {
    "Activos": {"analizado", "informe_generado", "informe_listo"},
    "En curso": {"geocodificando", "geocodificado", "analizando"},
    "Revisión": {"requiere_revision", "error"},
    "Borrador": {"borrador"},
}


# ── Stat card ─────────────────────────────────────────────────────────────────

class _StatCard(QWidget if PYSIDE6_AVAILABLE else object):
    def __init__(self, label: str, value: str, color: str = ACCENT) -> None:
        super().__init__()  # type: ignore[call-arg]
        self.setFixedHeight(72)
        self.setStyleSheet(
            f"background:{MARBLE_PANEL};border:1px solid {MARBLE_BORDER};"
            f"border-radius:6px;"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(2)

        val_lbl = QLabel(value)
        val_lbl.setStyleSheet(
            f"font-size:24px;font-weight:700;color:{color};"
            f"background:transparent;border:none;"
        )
        lbl_lbl = QLabel(label)
        lbl_lbl.setStyleSheet(
            f"font-size:10px;color:{TEXT_SUB};background:transparent;border:none;"
        )
        lay.addWidget(val_lbl)
        lay.addWidget(lbl_lbl)


# ── Expediente card ───────────────────────────────────────────────────────────

class _ExpCard(QFrame if PYSIDE6_AVAILABLE else object):
    """Clickable card for one expediente."""

    clicked = Signal(str) if PYSIDE6_AVAILABLE else None  # emits expediente id

    def __init__(self, exp: Any) -> None:
        super().__init__()  # type: ignore[call-arg]
        self._exp_id = exp.id
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        status = exp.status or "borrador"
        colour = _STATUS_COLOUR.get(status, TEXT_FAINT)
        badge = _STATUS_LABEL.get(status, status)

        self.setStyleSheet(
            f"QFrame{{background:{MARBLE_PANEL};border:1px solid {MARBLE_BORDER};"
            f"border-radius:8px;}} "
            f"QFrame:hover{{border:1px solid {ACCENT};background:{MARBLE_WARM};}}"
        )
        self.setFixedHeight(88)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)

        # Status stripe
        stripe = QFrame()
        stripe.setFixedWidth(4)
        stripe.setStyleSheet(
            f"background:{colour};border-radius:2px;border:none;"
        )
        lay.addWidget(stripe)

        # Text block
        info = QVBoxLayout()
        info.setSpacing(3)

        title_lbl = QLabel(exp.title[:50] + ("…" if len(exp.title) > 50 else ""))
        title_lbl.setStyleSheet(
            "font-size:13px;font-weight:600;color:#1C1C1A;background:transparent;border:none;"
        )

        loc = f"{exp.municipality} ({exp.province})" if exp.municipality else "Sin ubicación"
        loc_lbl = QLabel(loc)
        loc_lbl.setStyleSheet(
            f"font-size:10px;color:{TEXT_SUB};background:transparent;border:none;"
        )

        badge_lbl = QLabel(badge)
        badge_lbl.setStyleSheet(
            f"font-size:9px;font-weight:600;color:{colour};"
            f"background:transparent;border:none;"
        )

        info.addWidget(title_lbl)
        info.addWidget(loc_lbl)
        info.addWidget(badge_lbl)
        lay.addLayout(info, 1)

        # Arrow
        arrow = QLabel("›")
        arrow.setStyleSheet(
            f"font-size:20px;color:{TEXT_FAINT};background:transparent;border:none;"
        )
        lay.addWidget(arrow)

    def mousePressEvent(self, ev: Any) -> None:
        self.clicked.emit(self._exp_id)
        super().mousePressEvent(ev)


# ── Main Dashboard widget ─────────────────────────────────────────────────────

class ExpedientesDashboard(QWidget if PYSIDE6_AVAILABLE else object):
    """Full dashboard: stat bar + filtered expediente cards grid.

    Signals
    -------
    expediente_selected(str)  — emitted when user clicks a card (expediente id)
    new_requested()           — emitted when user clicks the New button
    """

    expediente_selected = Signal(str) if PYSIDE6_AVAILABLE else None
    new_requested = Signal() if PYSIDE6_AVAILABLE else None

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)  # type: ignore[call-arg]
        self._expedientes: list[Any] = []

        self.setStyleSheet(f"background:{MARBLE_BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # ── Header row ─────────────────────────────────────────────────────
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        title_lbl = QLabel("Expedientes")
        title_lbl.setStyleSheet(
            "font-size:20px;font-weight:700;color:#1C1C1A;"
        )
        header_row.addWidget(title_lbl)
        header_row.addStretch(1)

        self._new_btn = QPushButton("+ Nuevo expediente")
        self._new_btn.setFixedHeight(34)
        self._new_btn.setStyleSheet(
            f"QPushButton{{background:{ACCENT};color:#1C1C1A;font-weight:600;"
            f"font-size:12px;border:none;border-radius:6px;padding:0 16px;}}"
            f"QPushButton:hover{{background:#D8B84A;}}"
        )
        self._new_btn.clicked.connect(self.new_requested.emit)
        header_row.addWidget(self._new_btn)
        root.addLayout(header_row)

        # ── Stat bar ───────────────────────────────────────────────────────
        self._stat_row = QHBoxLayout()
        self._stat_row.setSpacing(10)
        self._stat_total   = _StatCard("Total", "0")
        self._stat_activos = _StatCard("Activos", "0", OK)
        self._stat_curso   = _StatCard("En curso", "0", ACCENT)
        self._stat_revision = _StatCard("Revisión", "0", WARN)
        for w in (self._stat_total, self._stat_activos, self._stat_curso, self._stat_revision):
            self._stat_row.addWidget(w)
        root.addLayout(self._stat_row)

        # ── Filter tabs ────────────────────────────────────────────────────
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        self._filter_btns: dict[str, QPushButton] = {}
        for label in ("Todos", "Activos", "En curso", "Revisión", "Borrador"):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            btn.setStyleSheet(
                f"QPushButton{{background:transparent;color:{TEXT_SUB};font-size:11px;"
                f"border:1px solid {MARBLE_BORDER};border-radius:14px;padding:0 12px;}}"
                f"QPushButton:checked{{background:{ACCENT};color:#1C1C1A;font-weight:600;"
                f"border:1px solid {ACCENT};}}"
                f"QPushButton:hover:!checked{{border:1px solid {ACCENT};color:#1C1C1A;}}"
            )
            btn.clicked.connect(lambda _, lbl=label: self._apply_filter(lbl))
            self._filter_btns[label] = btn
            filter_row.addWidget(btn)
        filter_row.addStretch(1)
        self._filter_btns["Todos"].setChecked(True)
        self._active_filter = "Todos"
        root.addLayout(filter_row)

        # ── Scrollable card grid ───────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background:{MARBLE_BG};border:none;")

        self._cards_container = QWidget()
        self._cards_container.setStyleSheet(f"background:{MARBLE_BG};")
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(8)
        self._cards_layout.addStretch(1)

        scroll.setWidget(self._cards_container)
        root.addWidget(scroll, 1)

        # ── Empty state ────────────────────────────────────────────────────
        self._empty_lbl = QLabel(
            "No hay expedientes.\nPulsa «+ Nuevo expediente» para crear el primero."
        )
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(
            f"font-size:13px;color:{TEXT_FAINT};background:{MARBLE_BG};"
        )
        self._empty_lbl.setVisible(False)
        root.addWidget(self._empty_lbl)

    # ── Public API ────────────────────────────────────────────────────────

    def load_expedientes(self, expedientes: list[Any]) -> None:
        """Populate the dashboard with the given expediente list."""
        self._expedientes = expedientes
        self._update_stats()
        self._rebuild_cards()

    def refresh(self, store: Any) -> None:
        """Re-load from an ExpedienteStore instance."""
        try:
            exps = store.list_all()
        except Exception:
            exps = []
        self.load_expedientes(exps)

    # ── Internal ──────────────────────────────────────────────────────────

    def _update_stats(self) -> None:
        total = len(self._expedientes)
        activos = sum(
            1 for e in self._expedientes
            if (e.status or "borrador") in _STATUS_GROUPS["Activos"]
        )
        curso = sum(
            1 for e in self._expedientes
            if (e.status or "borrador") in _STATUS_GROUPS["En curso"]
        )
        revision = sum(
            1 for e in self._expedientes
            if (e.status or "borrador") in _STATUS_GROUPS["Revisión"]
        )
        _set_stat(self._stat_total,   "Total",    str(total))
        _set_stat(self._stat_activos, "Activos",  str(activos), OK)
        _set_stat(self._stat_curso,   "En curso", str(curso), ACCENT)
        _set_stat(self._stat_revision,"Revisión", str(revision), WARN)

    def _apply_filter(self, label: str) -> None:
        for lbl, btn in self._filter_btns.items():
            btn.setChecked(lbl == label)
        self._active_filter = label
        self._rebuild_cards()

    def _rebuild_cards(self) -> None:
        lay = self._cards_layout
        # remove all cards (not the trailing stretch)
        while lay.count() > 1:
            item = lay.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        filtered = _filter_exps(self._expedientes, self._active_filter)

        self._empty_lbl.setVisible(len(filtered) == 0)

        for exp in filtered:
            card = _ExpCard(exp)
            card.clicked.connect(self.expediente_selected.emit)
            lay.insertWidget(lay.count() - 1, card)


def _set_stat(card: _StatCard, label: str, value: str, color: str = ACCENT) -> None:
    children = card.findChildren(QLabel)
    if len(children) >= 2:
        children[0].setText(value)
        children[0].setStyleSheet(
            f"font-size:24px;font-weight:700;color:{color};"
            f"background:transparent;border:none;"
        )
        children[1].setText(label)


def _filter_exps(exps: list[Any], label: str) -> list[Any]:
    if label == "Todos":
        return exps
    group = _STATUS_GROUPS.get(label, set())
    return [e for e in exps if (e.status or "borrador") in group]
