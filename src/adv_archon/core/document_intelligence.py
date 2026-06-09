from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from io import StringIO
from pathlib import PurePath
from typing import Any

from adv_archon.core.document_draft import DocumentDraft, DraftSection, DraftTable

DELIVERABLE_KINDS = ("report", "docx", "xlsx", "pdf", "presentation", "table")

_INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "report": (
        "informe",
        "memoria",
        "report",
        "resumen ejecutivo",
        "analisis",
        "dictamen",
    ),
    "docx": ("docx", "word", "documento editable", "documento word", "contrato"),
    "xlsx": ("xlsx", "excel", "hoja de calculo", "spreadsheet", "presupuesto", "modelo"),
    "pdf": ("pdf", "entrega final", "presentar", "exportar", "imprimir"),
    "presentation": ("pptx", "presentacion", "diapositiva", "slides", "deck", "powerpoint"),
    "table": ("tabla", "csv", "tsv", "listado", "dataset", "columnas", "filas"),
}
_EXTENSION_INTENTS = {
    ".docx": "docx",
    ".doc": "docx",
    ".xlsx": "xlsx",
    ".xls": "xlsx",
    ".csv": "table",
    ".tsv": "table",
    ".pdf": "pdf",
    ".pptx": "presentation",
    ".ppt": "presentation",
}
_DELIMITERS = ("\t", ";", ",", "|")
_ASSIGNMENT_RE = re.compile(
    r"(?P<label>[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][\wÁÉÍÓÚÜÑáéíóúüñ /().-]{0,42})"
    r"\s*=\s*(?P<expression>[^\n;]+)",
    re.IGNORECASE,
)
_MAGNITUDE_RE = re.compile(
    r"(?P<label>[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ /().-]{0,48})?"
    r"(?P<value>-?\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>m2|m²|m3|m³|kg|g|t|tn|eur|€|usd|\$|%|h|horas?|dias?|días?|"
    r"mm|cm|m|km|l|kw|kwh|hab|ud|uds)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class DeliverableIntent:
    kind: str
    confidence: float
    scores: dict[str, float]
    signals: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FormulaSignal:
    expression: str
    label: str = ""

    def as_payload(self) -> dict[str, str]:
        return {"label": self.label, "expression": self.expression}


@dataclass(frozen=True, slots=True)
class MagnitudeSignal:
    raw: str
    value: float
    unit: str
    label: str = ""

    def as_payload(self) -> dict[str, Any]:
        return {
            "raw": self.raw,
            "value": self.value,
            "unit": self.unit,
            "label": self.label,
        }


@dataclass(frozen=True, slots=True)
class DocumentIntelligenceResult:
    intent: DeliverableIntent
    tables: tuple[DraftTable, ...]
    formulas: tuple[FormulaSignal, ...]
    magnitudes: tuple[MagnitudeSignal, ...]
    draft: DocumentDraft
    next_steps: tuple[str, ...]


def classify_deliverable_intent(
    text: str,
    attachment_names: tuple[str, ...] | list[str] = (),
) -> DeliverableIntent:
    """Classify the likely deliverable target using local text and filename hints."""

    normalized = _normalize(text)
    scores = {kind: 0.0 for kind in DELIVERABLE_KINDS}
    signals: list[str] = []
    for kind, keywords in _INTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in normalized:
                scores[kind] += 1.0
                signals.append(f"{kind}:{keyword}")

    for name in attachment_names:
        suffix = PurePath(name).suffix.lower()
        extension_kind = _EXTENSION_INTENTS.get(suffix)
        if extension_kind:
            scores[extension_kind] += 2.0
            signals.append(f"{extension_kind}:{suffix}")

    if _looks_tabular(text):
        scores["table"] += 1.5
        signals.append("table:structured-text")
    if detect_formulas(text):
        scores["xlsx"] += 1.0
        signals.append("xlsx:formula")

    kind = max(DELIVERABLE_KINDS, key=lambda item: (scores[item], -DELIVERABLE_KINDS.index(item)))
    if scores[kind] <= 0:
        kind = "report"
        signals.append("report:default")
    confidence = _confidence(scores[kind], sum(scores.values()))
    return DeliverableIntent(
        kind=kind,
        confidence=confidence,
        scores={item: round(scores[item], 3) for item in DELIVERABLE_KINDS},
        signals=tuple(dict.fromkeys(signals)),
    )


def extract_tabular_data(text: str, *, title: str = "Datos detectados") -> tuple[DraftTable, ...]:
    """Extract simple CSV/TSV/markdown-like tables into DraftTable objects."""

    tables: list[DraftTable] = []
    seen: set[tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]] = set()
    for index, rows in enumerate(_iter_table_blocks(text), start=1):
        if len(rows) < 2:
            continue
        width = max(len(row) for row in rows)
        padded = tuple(
            tuple(_cell(row[idx]) if idx < len(row) else "" for idx in range(width))
            for row in rows
        )
        columns = padded[0]
        body = padded[1:]
        if not any(any(cell for cell in row) for row in body):
            continue
        key = (columns, body)
        if key in seen:
            continue
        seen.add(key)
        tables.append(
            DraftTable(
                id=f"detected-table-{index}",
                title=title if len(tables) == 0 else f"{title} {len(tables) + 1}",
                columns=columns,
                rows=body,
            )
        )
    return tuple(tables)


def detect_formulas(text: str) -> tuple[FormulaSignal, ...]:
    formulas: list[FormulaSignal] = []
    seen: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = re.split(
            r"(?<=[.;])\s+(?=[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][^=]{0,42}\s*=)",
            stripped,
        )
        for part in parts:
            for match in _ASSIGNMENT_RE.finditer(part):
                label = _label_from_prefix(match.group("label"))
                expression = _clean_formula(match.group("expression"))
                if not _is_formula_like(expression) or expression.lower() in seen:
                    continue
                seen.add(expression.lower())
                formulas.append(FormulaSignal(expression=expression, label=label))
            if formulas:
                continue
    return tuple(formulas)


def detect_magnitudes(text: str) -> tuple[MagnitudeSignal, ...]:
    magnitudes: list[MagnitudeSignal] = []
    seen: set[tuple[str, str, str]] = set()
    for match in _MAGNITUDE_RE.finditer(text):
        raw = _cell(match.group(0))
        unit = _cell(match.group("unit")).replace("²", "2").replace("³", "3")
        label = _label_from_prefix(match.group("label") or "")
        value = _parse_number(match.group("value"))
        key = (raw.lower(), unit.lower(), label.lower())
        if key in seen:
            continue
        seen.add(key)
        magnitudes.append(MagnitudeSignal(raw=raw, value=value, unit=unit, label=label))
    return tuple(magnitudes)


def build_document_intelligence_draft(
    text: str,
    *,
    attachment_names: tuple[str, ...] | list[str] = (),
    title: str | None = None,
) -> DocumentDraft:
    intent = classify_deliverable_intent(text, attachment_names)
    tables = extract_tabular_data(text)
    formulas = detect_formulas(text)
    magnitudes = detect_magnitudes(text)
    next_steps = propose_dispatch_next_steps(
        intent=intent,
        tables=tables,
        formulas=formulas,
        magnitudes=magnitudes,
    )
    return _draft_from_signals(
        text=text,
        title=title or _suggest_title(intent),
        intent=intent,
        tables=tables,
        formulas=formulas,
        magnitudes=magnitudes,
        next_steps=next_steps,
    )


def propose_dispatch_next_steps(
    *,
    intent: DeliverableIntent,
    tables: tuple[DraftTable, ...] = (),
    formulas: tuple[FormulaSignal, ...] = (),
    magnitudes: tuple[MagnitudeSignal, ...] = (),
) -> tuple[str, ...]:
    steps: list[str] = []
    if intent.kind in {"xlsx", "table"}:
        steps.append("Preparar tabla auditable y revisar tipos de dato antes de exportar.")
    elif intent.kind == "presentation":
        steps.append("Convertir el borrador en guion de diapositivas y validar mensajes clave.")
    elif intent.kind == "pdf":
        steps.append("Revisar el borrador editable antes de generar PDF final.")
    elif intent.kind == "docx":
        steps.append("Generar DOCX editable y dejar trazables tablas, formulas y supuestos.")
    else:
        steps.append("Completar el informe preliminar y revisar tono, alcance y destinatario.")

    if tables:
        steps.append(
            f"Validar {len(tables)} tabla(s) detectada(s): cabeceras, unidades y filas "
            "incompletas."
        )
    if formulas:
        steps.append(
            f"Auditar {len(formulas)} formula(s) detectada(s) antes de usarlas en calculos."
        )
    if magnitudes:
        steps.append(f"Comprobar unidades de {len(magnitudes)} magnitud(es) detectada(s).")
    if intent.confidence < 0.45:
        steps.append("Confirmar formato de salida porque la intencion detectada es debil.")
    return tuple(steps)


def analyze_document_intelligence(
    text: str,
    *,
    attachment_names: tuple[str, ...] | list[str] = (),
    title: str | None = None,
) -> DocumentIntelligenceResult:
    intent = classify_deliverable_intent(text, attachment_names)
    tables = extract_tabular_data(text)
    formulas = detect_formulas(text)
    magnitudes = detect_magnitudes(text)
    next_steps = propose_dispatch_next_steps(
        intent=intent,
        tables=tables,
        formulas=formulas,
        magnitudes=magnitudes,
    )
    draft = _draft_from_signals(
        text=text,
        title=title or _suggest_title(intent),
        intent=intent,
        tables=tables,
        formulas=formulas,
        magnitudes=magnitudes,
        next_steps=next_steps,
    )
    return DocumentIntelligenceResult(
        intent=intent,
        tables=tables,
        formulas=formulas,
        magnitudes=magnitudes,
        draft=draft,
        next_steps=next_steps,
    )


def _draft_from_signals(
    *,
    text: str,
    title: str,
    intent: DeliverableIntent,
    tables: tuple[DraftTable, ...],
    formulas: tuple[FormulaSignal, ...],
    magnitudes: tuple[MagnitudeSignal, ...],
    next_steps: tuple[str, ...],
) -> DocumentDraft:
    summary = _summary(text)
    sections = [
        DraftSection(id="summary", title="Resumen inicial", content=summary),
        DraftSection(
            id="source-text",
            title="Texto analizado",
            content=text.strip()[:3000] or "Sin texto de entrada.",
            include_in_report=False,
        ),
    ]
    if formulas:
        sections.append(
            DraftSection(
                id="formulas",
                title="Formulas detectadas",
                content="\n".join(
                    f"- {item.label + ': ' if item.label else ''}{item.expression}"
                    for item in formulas
                ),
            )
        )
    if magnitudes:
        sections.append(
            DraftSection(
                id="magnitudes",
                title="Magnitudes detectadas",
                content="\n".join(
                    f"- {item.label + ': ' if item.label else ''}{item.raw}" for item in magnitudes
                ),
            )
        )
    warnings = []
    if formulas:
        warnings.append(
            "Formulas detectadas automaticamente: revisar sintaxis, unidades y supuestos."
        )
    if tables:
        warnings.append(
            "Tablas extraidas de texto plano: revisar cabeceras y celdas antes de entregar."
        )
    if not warnings:
        warnings.append("Borrador generado con heuristicas locales; requiere revision humana.")

    return DocumentDraft(
        kind="document_intelligence",
        title=title,
        verdict="BORRADOR",
        executive_summary=summary,
        sections=tuple(sections),
        tables=tables,
        warnings=tuple(warnings),
        next_steps=next_steps,
        metadata={
            "deliverable_intent": intent.kind,
            "intent_confidence": intent.confidence,
            "intent_signals": list(intent.signals),
            "formula_count": len(formulas),
            "magnitude_count": len(magnitudes),
            "table_count": len(tables),
            "formulas": [item.as_payload() for item in formulas],
            "magnitudes": [item.as_payload() for item in magnitudes],
        },
    )


def _iter_table_blocks(text: str) -> tuple[tuple[tuple[str, ...], ...], ...]:
    lines = [line.rstrip() for line in text.splitlines()]
    blocks: list[tuple[tuple[str, ...], ...]] = []
    current: list[str] = []
    current_delimiter = ""
    for line in lines + [""]:
        delimiter = _dominant_delimiter(line)
        if delimiter and (not current_delimiter or delimiter == current_delimiter):
            current.append(line)
            current_delimiter = delimiter
            continue
        if current:
            rows = _parse_delimited_rows(current, current_delimiter)
            if rows:
                blocks.append(rows)
        current = [line] if delimiter else []
        current_delimiter = delimiter
    return tuple(blocks)


def _parse_delimited_rows(lines: list[str], delimiter: str) -> tuple[tuple[str, ...], ...]:
    cleaned = [line for line in lines if not _is_markdown_separator(line, delimiter)]
    if len(cleaned) < 2:
        return ()
    if delimiter == "|":
        rows = tuple(_parse_pipe_line(line) for line in cleaned)
    else:
        reader = csv.reader(StringIO("\n".join(cleaned)), delimiter=delimiter)
        rows = tuple(tuple(_cell(cell) for cell in row) for row in reader)
    widths = [len(row) for row in rows if len(row) > 1]
    if len(widths) < 2 or max(widths) - min(widths) > 1:
        return ()
    return rows


def _dominant_delimiter(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""
    counts = {delimiter: stripped.count(delimiter) for delimiter in _DELIMITERS}
    delimiter, count = max(counts.items(), key=lambda item: item[1])
    if count <= 0:
        return ""
    if delimiter == "|" and count == 1:
        return ""
    return delimiter


def _parse_pipe_line(line: str) -> tuple[str, ...]:
    stripped = line.strip().strip("|")
    return tuple(_cell(cell) for cell in stripped.split("|"))


def _is_markdown_separator(line: str, delimiter: str) -> bool:
    if delimiter != "|":
        return False
    stripped = line.strip().strip("|").replace(" ", "").replace("|", "")
    return bool(stripped) and set(stripped) <= {"-", ":"}


def _looks_tabular(text: str) -> bool:
    return bool(_iter_table_blocks(text))


def _normalize(text: str) -> str:
    replacements = str.maketrans(
        {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u", "ñ": "n"}
    )
    return text.lower().translate(replacements)


def _confidence(winning_score: float, total_score: float) -> float:
    if winning_score <= 0:
        return 0.0
    if total_score <= 0:
        return 0.3
    return round(min(0.95, max(0.25, winning_score / total_score)), 3)


def _clean_formula(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip(" .;:"))


def _is_formula_like(value: str) -> bool:
    compact = value.replace(" ", "")
    if len(compact) < 5:
        return False
    return any(token in compact for token in ("=", "*", "/", "^", ">=", "<="))


def _parse_number(value: str) -> float:
    return float(value.replace(",", "."))


def _label_from_prefix(value: str) -> str:
    cleaned = _cell(value)
    cleaned = re.sub(r"^[^\wÁÉÍÓÚÜÑáéíóúüñ]+", "", cleaned)
    return cleaned[-48:].strip(" :-")


def _summary(text: str) -> str:
    stripped = " ".join(text.strip().split())
    if not stripped:
        return "Borrador inicial pendiente de contenido."
    return stripped[:700]


def _suggest_title(intent: DeliverableIntent) -> str:
    labels = {
        "report": "Borrador de informe",
        "docx": "Borrador de documento editable",
        "xlsx": "Borrador de libro auditable",
        "pdf": "Borrador para PDF",
        "presentation": "Borrador de presentacion",
        "table": "Borrador de tabla de datos",
    }
    return labels.get(intent.kind, "Borrador documental")


def _cell(value: Any) -> str:
    return str(value or "").strip()


__all__ = [
    "DeliverableIntent",
    "DocumentIntelligenceResult",
    "FormulaSignal",
    "MagnitudeSignal",
    "analyze_document_intelligence",
    "build_document_intelligence_draft",
    "classify_deliverable_intent",
    "detect_formulas",
    "detect_magnitudes",
    "extract_tabular_data",
    "propose_dispatch_next_steps",
]
