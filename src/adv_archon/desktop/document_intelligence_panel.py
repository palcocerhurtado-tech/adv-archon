# mypy: ignore-errors
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from html import escape
from importlib import import_module
from importlib.util import find_spec
from typing import Any

PYSIDE6_AVAILABLE = find_spec("PySide6") is not None

Qt: Any = None
Signal: Any = None
QFrame: Any = None
QHBoxLayout: Any = None
QLabel: Any = None
QPushButton: Any = None
QTextBrowser: Any = None
QVBoxLayout: Any = None

if PYSIDE6_AVAILABLE:
    _qt_core = import_module("PySide6.QtCore")
    _qt_widgets = import_module("PySide6.QtWidgets")
    Qt = _qt_core.Qt
    Signal = _qt_core.Signal
    QFrame = _qt_widgets.QFrame
    QHBoxLayout = _qt_widgets.QHBoxLayout
    QLabel = _qt_widgets.QLabel
    QPushButton = _qt_widgets.QPushButton
    QTextBrowser = _qt_widgets.QTextBrowser
    QVBoxLayout = _qt_widgets.QVBoxLayout


@dataclass(frozen=True, slots=True)
class DocumentIntelligenceSummary:
    intent: str
    confidence: float
    signals: tuple[str, ...]
    table_count: int
    formula_count: int
    magnitude_count: int
    draft_title: str
    next_steps: tuple[str, ...]
    table_lines: tuple[str, ...]
    formula_lines: tuple[str, ...]
    magnitude_lines: tuple[str, ...]


def draft_to_intelligence_text(draft: Mapping[str, Any] | Any) -> str:
    """Build a compact local-analysis text from a draft-like object."""

    parts: list[str] = []
    for key in ("title", "project_name", "executive_summary", "verdict"):
        value = _get_value(draft, key, default="")
        if value:
            parts.append(f"{key}: {value}")

    for section in _as_sequence(_get_value(draft, "sections", default=())):
        title = _get_value(section, "title", default="")
        content = _get_value(section, "content", default="")
        if title or content:
            parts.append(f"\n## {title}\n{content}".strip())

    for table in _as_sequence(_get_value(draft, "tables", default=())):
        title = _get_value(table, "title", default="Tabla")
        columns = [str(item) for item in _as_sequence(_get_value(table, "columns", default=()))]
        rows = _as_sequence(_get_value(table, "rows", default=()))
        if columns:
            parts.append(f"\n## {title}\n" + ",".join(columns))
        for row in rows[:20]:
            parts.append(",".join(str(cell) for cell in _as_sequence(row)))

    metadata = _get_value(draft, "metadata", default={})
    if isinstance(metadata, Mapping):
        formulas = metadata.get("formulas") or ()
        magnitudes = metadata.get("magnitudes") or ()
        for item in _as_sequence(formulas):
            label = _get_value(item, "label", default="")
            expression = _get_value(item, "expression", default="")
            if expression:
                parts.append(f"Formula {label}: {expression}")
        for item in _as_sequence(magnitudes):
            raw = _get_value(item, "raw", default="")
            if raw:
                parts.append(f"Magnitud: {raw}")

    for label, key in (("Advertencia", "warnings"), ("Siguiente paso", "next_steps")):
        for item in _as_sequence(_get_value(draft, key, default=())):
            if item:
                parts.append(f"{label}: {item}")

    return "\n".join(str(part) for part in parts if str(part).strip())


def summarize_document_intelligence(
    result: Mapping[str, Any] | Any,
) -> DocumentIntelligenceSummary:
    """Normalize a DocumentIntelligenceResult/tool payload for UI rendering."""

    intent_value = _get_value(result, "intent", default="")
    if isinstance(intent_value, Mapping) or hasattr(intent_value, "kind"):
        intent = str(_get_value(intent_value, "kind", default="report"))
        confidence = _to_float(_get_value(intent_value, "confidence", default=0.0))
        signals = tuple(
            str(item)
            for item in _as_sequence(_get_value(intent_value, "signals", default=()))
        )
    else:
        intent = str(intent_value or "report")
        confidence = _to_float(_get_value(result, "confidence", default=0.0))
        signals = tuple(
            str(item)
            for item in _as_sequence(_get_value(result, "signals", default=()))
        )

    tables = tuple(_as_sequence(_get_value(result, "tables", default=())))
    formulas = tuple(_as_sequence(_get_value(result, "formulas", default=())))
    magnitudes = tuple(_as_sequence(_get_value(result, "magnitudes", default=())))
    draft = _get_value(result, "draft", default={})
    next_steps = tuple(
        str(item)
        for item in _as_sequence(_get_value(result, "next_steps", default=()))
        if str(item).strip()
    )

    return DocumentIntelligenceSummary(
        intent=intent,
        confidence=confidence,
        signals=signals,
        table_count=len(tables),
        formula_count=len(formulas),
        magnitude_count=len(magnitudes),
        draft_title=str(_get_value(draft, "title", default="Borrador generado")),
        next_steps=next_steps,
        table_lines=tuple(_table_line(item) for item in tables[:6]),
        formula_lines=tuple(_formula_line(item) for item in formulas[:8]),
        magnitude_lines=tuple(_magnitude_line(item) for item in magnitudes[:10]),
    )


def analyze_draft_for_panel(
    draft: Mapping[str, Any] | Any,
    *,
    attachment_names: Sequence[str] = (),
) -> Any:
    """Run local Document Intelligence over an editable draft."""

    from adv_archon.core.document_intelligence import analyze_document_intelligence

    return analyze_document_intelligence(
        draft_to_intelligence_text(draft),
        attachment_names=list(attachment_names),
        title=str(_get_value(draft, "title", default="Borrador generado")),
    )


if PYSIDE6_AVAILABLE:

    class DocumentIntelligencePanel(QFrame):  # type: ignore[misc]
        export_requested = Signal(str)

        def __init__(self, parent: Any | None = None) -> None:
            super().__init__(parent)
            self.setObjectName("Panel")
            self._summary: DocumentIntelligenceSummary | None = None

            layout = QVBoxLayout(self)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(8)

            header = QHBoxLayout()
            title = QLabel("Document Intelligence")
            title.setObjectName("StudioCase")
            self._badge = QLabel("Pendiente")
            self._badge.setObjectName("Faint")
            header.addWidget(title)
            header.addStretch(1)
            header.addWidget(self._badge)
            layout.addLayout(header)

            self._stats = QLabel("Tablas 0 · Formulas 0 · Magnitudes 0")
            self._stats.setObjectName("Faint")
            self._stats.setWordWrap(True)
            layout.addWidget(self._stats)

            self._browser = QTextBrowser()
            self._browser.setMinimumHeight(170)
            self._browser.setOpenExternalLinks(False)
            layout.addWidget(self._browser, 1)

            actions = QHBoxLayout()
            self._buttons: dict[str, Any] = {}
            for kind, label in (("pdf", "PDF"), ("docx", "DOCX"), ("xlsx", "XLSX")):
                button = QPushButton(f"Exportar {label}")
                button.setObjectName("Primary" if kind == "pdf" else "Ghost")
                button.clicked.connect(
                    lambda _checked=False, value=kind: self.export_requested.emit(value)
                )
                button.setEnabled(False)
                self._buttons[kind] = button
                actions.addWidget(button)
            layout.addLayout(actions)
            self.set_empty("Analiza un borrador o ejecuta Research para ver señales.")

        def set_empty(self, message: str) -> None:
            self._summary = None
            self._badge.setText("Pendiente")
            self._stats.setText("Tablas 0 · Formulas 0 · Magnitudes 0")
            self._browser.setHtml(f"<p style='color:#7A7568;'>{escape(message)}</p>")
            for button in self._buttons.values():
                button.setEnabled(False)

        def load_result(self, result: Mapping[str, Any] | Any) -> None:
            summary = summarize_document_intelligence(result)
            self._summary = summary
            confidence = int(round(summary.confidence * 100))
            self._badge.setText(f"{summary.intent.upper()} · {confidence}%")
            self._stats.setText(
                f"Tablas {summary.table_count} · "
                f"Formulas {summary.formula_count} · "
                f"Magnitudes {summary.magnitude_count}"
            )
            self._browser.setHtml(_summary_to_html(summary))
            for button in self._buttons.values():
                button.setEnabled(True)

        def analyze_draft(
            self,
            draft: Mapping[str, Any] | Any,
            *,
            attachment_names: Sequence[str] = (),
        ) -> None:
            self.load_result(
                analyze_draft_for_panel(draft, attachment_names=attachment_names)
            )

else:

    class DocumentIntelligencePanel:  # pragma: no cover - only used when Qt is missing
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("PySide6 no esta instalada. No se puede crear el panel.")


def _summary_to_html(summary: DocumentIntelligenceSummary) -> str:
    tables = _html_list(summary.table_lines, "Sin tablas estructuradas detectadas.")
    formulas = _html_list(summary.formula_lines, "Sin formulas detectadas.")
    magnitudes = _html_list(summary.magnitude_lines, "Sin magnitudes detectadas.")
    next_steps = _html_list(summary.next_steps, "Sin pasos adicionales.")
    signals = ", ".join(summary.signals[:5]) or "analisis local"
    return f"""
    <div style="font-size:11px;">
      <p><b>Borrador generado:</b> {escape(summary.draft_title)}</p>
      <p><b>Señales:</b> {escape(signals)}</p>
      <h4>Tablas detectadas</h4>{tables}
      <h4>Formulas</h4>{formulas}
      <h4>Magnitudes</h4>{magnitudes}
      <h4>Siguiente accion</h4>{next_steps}
    </div>
    """


def _html_list(items: Sequence[str], empty: str) -> str:
    if not items:
        return f"<p style='color:#7A7568;'>{escape(empty)}</p>"
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"


def _table_line(item: Any) -> str:
    title = str(_get_value(item, "title", default="Tabla"))
    columns = tuple(str(value) for value in _as_sequence(_get_value(item, "columns", default=())))
    rows = tuple(_as_sequence(_get_value(item, "rows", default=())))
    column_text = ", ".join(columns[:5]) if columns else "sin cabeceras"
    return f"{title}: {len(rows)} fila(s), columnas {column_text}"


def _formula_line(item: Any) -> str:
    label = str(_get_value(item, "label", default="")).strip()
    expression = str(_get_value(item, "expression", default="")).strip()
    return f"{label}: {expression}" if label else expression or "Formula detectada"


def _magnitude_line(item: Any) -> str:
    raw = str(_get_value(item, "raw", default="")).strip()
    label = str(_get_value(item, "label", default="")).strip()
    return f"{label}: {raw}" if label and raw else raw or "Magnitud detectada"


def _get_value(source: Mapping[str, Any] | Any, name: str, *, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(name, default)
    if hasattr(source, name):
        return getattr(source, name)
    return default


def _as_sequence(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(value)
    return (value,)


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


__all__ = [
    "DocumentIntelligencePanel",
    "DocumentIntelligenceSummary",
    "analyze_draft_for_panel",
    "draft_to_intelligence_text",
    "summarize_document_intelligence",
]
