from __future__ import annotations

import json
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF, XPos, YPos

# ── Font paths ────────────────────────────────────────────────────────────────
_FONT_REGULAR_CANDIDATES = [
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
]
_FONT_BOLD_CANDIDATES = [
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]

# ── Palette ──────────────────────────────────────────────────────────────────
_C_BLACK = (30, 30, 30)
_C_DARK = (50, 50, 80)
_C_ACCENT = (40, 80, 160)
_C_LIGHT_BG = (245, 247, 252)
_C_OK = (34, 139, 34)
_C_WARN = (200, 120, 0)
_C_ERR = (190, 30, 30)
_C_INFO = (80, 80, 160)
_C_BORDER = (200, 205, 220)
_C_WHITE = (255, 255, 255)
_C_HEADER_BG = (40, 80, 160)
_C_ROW_ALT = (238, 242, 252)

_STATUS_COLOR = {
    "ok": _C_OK,
    "warning": _C_WARN,
    "violation": _C_ERR,
    "info": _C_INFO,
}
_STATUS_LABEL = {
    "ok": "CUMPLE",
    "warning": "REVISAR",
    "violation": "INCUMPLE",
    "info": "INFO",
}
_STATUS_SYMBOL = {
    "ok": "OK",
    "warning": "REV",
    "violation": "NOK",
    "info": "INF",
}


@dataclass
class ReportSection:
    title: str
    rows: list[tuple[str, str, str, str]]  # (parametro, valor, normativa, status)
    notes: list[str]


class ArchonPDF(FPDF):
    def __init__(self, municipality: str, plan_name: str) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.municipality = municipality
        self.plan_name = plan_name
        self.set_margins(18, 18, 18)
        self.set_auto_page_break(auto=True, margin=22)
        regular = next((path for path in _FONT_REGULAR_CANDIDATES if path.exists()), None)
        bold = next((path for path in _FONT_BOLD_CANDIDATES if path.exists()), regular)
        if regular is not None:
            self.add_font("Archon", "", str(regular))
            self.add_font("Archon", "B", str(bold or regular))
            self._fn = "Archon"
        else:
            self._fn = "Helvetica"

    def header(self) -> None:
        self.set_fill_color(*_C_HEADER_BG)
        self.rect(0, 0, 210, 14, style="F")
        self.set_y(2)
        self.set_font(self._fn, "B", 9)
        self.set_text_color(*_C_WHITE)
        self.cell(0, 10, "ADV ARCHON  ·  INFORME DE CUMPLIMIENTO NORMATIVO URBANÍSTICO",
                  align="C")
        self.set_text_color(*_C_BLACK)
        self.ln(6)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_draw_color(*_C_BORDER)
        self.line(18, self.get_y(), 192, self.get_y())
        self.set_font(self._fn, "", 7)
        self.set_text_color(130, 130, 130)
        self.cell(
            0, 8,
            f"Generado por ADV ARCHON  ·  Análisis preliminar, no vinculante jurídicamente  ·  "
            f"Página {self.page_no()}",
            align="C",
        )
        self.set_text_color(*_C_BLACK)


def generate_compliance_pdf(
    *,
    plan_path: str,
    municipality: str,
    generated_at: str,
    summary: str,
    annotations: list[dict[str, Any]],
    full_analysis: str,
    output_path: Path,
) -> Path:
    plan_name = Path(plan_path).name
    pdf = ArchonPDF(municipality=municipality, plan_name=plan_name)
    pdf.add_page()

    # ── Title block ──────────────────────────────────────────────────────────
    pdf.set_font(pdf._fn, "B", 18)
    pdf.set_text_color(*_C_ACCENT)
    pdf.cell(0, 10, "INFORME DE CUMPLIMIENTO NORMATIVO", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(pdf._fn, "", 12)
    pdf.set_text_color(*_C_DARK)
    pdf.cell(
        0,
        7,
        _clean_text(f"Municipio: {municipality}"),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(3)

    # ── Metadata table ───────────────────────────────────────────────────────
    _meta_table(pdf, plan_name, municipality, generated_at)
    pdf.ln(6)

    # ── Executive summary ────────────────────────────────────────────────────
    _section_title(pdf, "RESUMEN EJECUTIVO")
    _summary_box(pdf, summary)
    pdf.ln(4)

    # ── Compliance annotations table ─────────────────────────────────────────
    if annotations:
        _section_title(pdf, "TABLA DE VERIFICACIÓN NORMATIVA")
        _annotations_table(pdf, annotations)
        pdf.ln(4)

    # ── Full analysis ────────────────────────────────────────────────────────
    _section_title(pdf, "ANÁLISIS DETALLADO")
    _full_analysis_block(pdf, full_analysis)

    # ── Legend ───────────────────────────────────────────────────────────────
    pdf.ln(4)
    _legend(pdf)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    return output_path


def _generate_expediente_pdf_legacy(
    *,
    expediente: Any,
    output_path: Path,
) -> Path:
    site_context = _loads_json(getattr(expediente, "site_context", ""))
    analysis = _loads_json(getattr(expediente, "analysis_result", ""))
    municipality = getattr(expediente, "municipality", "") or site_context.get(
        "municipality", ""
    )
    plan_path = getattr(expediente, "plan_path", "") or "Sin plano adjunto"

    pdf = ArchonPDF(municipality=municipality or "—", plan_name=Path(plan_path).name)
    pdf.add_page()

    pdf.set_font(pdf._fn, "B", 18)
    pdf.set_text_color(*_C_ACCENT)
    pdf.cell(0, 10, "EXPEDIENTE URBANÍSTICO PRELIMINAR", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(pdf._fn, "", 11)
    pdf.set_text_color(*_C_DARK)
    pdf.multi_cell(0, 6, _clean_text(getattr(expediente, "title", "")))
    pdf.set_text_color(*_C_BLACK)
    pdf.ln(3)

    _expediente_meta_table(pdf, expediente, site_context)
    pdf.ln(5)

    _section_title(pdf, "VEREDICTO EJECUTIVO")
    verdict = str(analysis.get("verdict") or "revisar").upper()
    summary = str(analysis.get("summary") or "Expediente pendiente de análisis completo.")
    _summary_box(pdf, f"{verdict}\n\n{summary}")
    pdf.ln(4)

    parcel_detail = site_context.get("parcel_detail") or {}
    if isinstance(parcel_detail, dict) and parcel_detail:
        _section_title(pdf, "CATASTRO")
        _simple_key_value_table(
            pdf,
            [
                (
                    "Referencia catastral",
                    getattr(expediente, "cadastral_ref", "")
                    or site_context.get("cadastral_ref", ""),
                ),
                (
                    "Dirección",
                    site_context.get("cadastral_address", "")
                    or getattr(expediente, "address", ""),
                ),
                (
                    "Uso",
                    parcel_detail.get("use_detail", "")
                    or site_context.get("cadastral_use", ""),
                ),
                ("Superficie construida", _fmt_optional(parcel_detail.get("surface_m2"), " m²")),
                ("Año construcción", str(parcel_detail.get("construction_year") or "")),
                ("Plantas sobre rasante", str(parcel_detail.get("floors_above") or "")),
            ],
        )
        pdf.ln(4)

    checks = site_context.get("legal_checks") or []
    if isinstance(checks, list) and checks:
        _section_title(pdf, "CHECKS SECTORIALES Y URBANÍSTICOS")
        _legal_checks_table(pdf, checks)
        pdf.ln(4)

    annotations = analysis.get("annotations") or []
    if isinstance(annotations, list) and annotations:
        _section_title(pdf, "ANOTACIONES DEL EXPEDIENTE")
        _annotations_table(pdf, annotations)
        pdf.ln(4)

    _section_title(pdf, "ADVERTENCIAS Y PRÓXIMOS PASOS")
    next_steps = analysis.get("next_steps") or []
    if not isinstance(next_steps, list) or not next_steps:
        next_steps = [
            "Confirmar la ordenanza exacta en planos de ordenación o visor municipal.",
            (
                "Revisar afecciones sectoriales con la administración competente "
                "si el expediente es sensible."
            ),
            "No usar este informe como certificado jurídico vinculante sin revisión técnica final.",
        ]
    _full_analysis_block(pdf, "\n".join(f"- {step}" for step in next_steps))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    return output_path


# ── Private helpers ───────────────────────────────────────────────────────────

def _loads_json(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _fmt_optional(value: Any, suffix: str = "") -> str:
    return f"{value}{suffix}" if value not in (None, "") else ""


def _expediente_meta_table(pdf: ArchonPDF, expediente: Any, site_context: dict[str, Any]) -> None:
    rows = [
        ("Dirección", getattr(expediente, "address", "")),
        (
            "Municipio",
            getattr(expediente, "municipality", "") or site_context.get("municipality", ""),
        ),
        ("Provincia", getattr(expediente, "province", "") or site_context.get("province", "")),
        (
            "Referencia catastral",
            getattr(expediente, "cadastral_ref", "")
            or site_context.get("cadastral_ref", ""),
        ),
        (
            "Coordenadas",
            _format_coords(
                getattr(expediente, "latitude", None) or site_context.get("latitude"),
                getattr(expediente, "longitude", None) or site_context.get("longitude"),
            ),
        ),
        ("Plano", Path(getattr(expediente, "plan_path", "") or "Sin plano").name),
        ("Fecha", datetime.now().strftime("%d/%m/%Y %H:%M")),
    ]
    _simple_key_value_table(pdf, rows)


def _format_coords(lat: Any, lon: Any) -> str:
    try:
        return f"{float(lat):.6f}, {float(lon):.6f}"
    except (TypeError, ValueError):
        return ""


def _simple_key_value_table(pdf: ArchonPDF, rows: list[tuple[str, Any]]) -> None:
    col_w = [48, 124]
    pdf.set_font(pdf._fn, "", 8)
    for label, value in rows:
        text = _clean_text(str(value or "—"))
        pdf.set_fill_color(*_C_LIGHT_BG)
        pdf.set_font(pdf._fn, "B", 8)
        pdf.cell(col_w[0], 6, f"  {_clean_text(label)}", border=1, fill=True)
        pdf.set_font(pdf._fn, "", 8)
        pdf.set_fill_color(*_C_WHITE)
        pdf.cell(col_w[1], 6, f"  {text[:95]}", border=1, fill=True,
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _legacy_legal_checks_table(pdf: ArchonPDF, checks: list[Any]) -> None:
    headers = ["Check", "Estado", "Detalle"]
    col_w = [54, 30, 90]
    pdf.set_fill_color(*_C_HEADER_BG)
    pdf.set_text_color(*_C_WHITE)
    pdf.set_font(pdf._fn, "B", 8)
    for header, width in zip(headers, col_w, strict=True):
        pdf.cell(width, 7, f"  {header}", border=1, fill=True)
    pdf.ln()
    pdf.set_text_color(*_C_BLACK)

    status_labels = {
        "ready": "OK",
        "conditional": "COND.",
        "pending_review": "REVISAR",
        "missing": "FALTA",
        "not_applicable": "N/A",
    }
    for idx, check in enumerate(checks[:12]):
        if not isinstance(check, dict):
            continue
        fill = _C_ROW_ALT if idx % 2 == 0 else _C_WHITE
        status = str(check.get("status") or "")
        pdf.set_fill_color(*fill)
        pdf.set_font(pdf._fn, "", 7)
        pdf.cell(col_w[0], 7, _clean_text(str(check.get("title") or ""))[:34], border=1, fill=True)
        pdf.cell(col_w[1], 7, status_labels.get(status, status)[:12], border=1, fill=True)
        pdf.cell(col_w[2], 7, _clean_text(str(check.get("detail") or ""))[:62], border=1, fill=True,
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

def _section_title(pdf: ArchonPDF, title: str) -> None:
    pdf.set_fill_color(*_C_LIGHT_BG)
    pdf.set_draw_color(*_C_ACCENT)
    pdf.set_line_width(0.5)
    pdf.set_font(pdf._fn, "B", 10)
    pdf.set_text_color(*_C_ACCENT)
    pdf.cell(0, 8, f"  {title}", border="LB", fill=True,
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_line_width(0.2)
    pdf.set_text_color(*_C_BLACK)
    pdf.ln(2)


def _meta_table(pdf: ArchonPDF, plan_name: str, municipality: str, generated_at: str) -> None:
    try:
        dt = datetime.fromisoformat(generated_at)
        fecha = dt.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        fecha = generated_at[:16]

    rows = [
        ("Plano analizado", plan_name),
        ("Municipio", municipality),
        ("Fecha de análisis", fecha),
    ]
    col_w = [50, 122]
    pdf.set_font(pdf._fn, "", 9)
    for label, value in rows:
        pdf.set_fill_color(*_C_LIGHT_BG)
        pdf.set_font(pdf._fn, "B", 9)
        pdf.cell(col_w[0], 7, f"  {label}", border=1, fill=True)
        pdf.set_font(pdf._fn, "", 9)
        pdf.set_fill_color(*_C_WHITE)
        pdf.cell(
            col_w[1],
            7,
            f"  {_clean_text(value)}",
            border=1,
            fill=True,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )


def _summary_box(pdf: ArchonPDF, summary: str) -> None:
    pdf.set_fill_color(*_C_LIGHT_BG)
    pdf.set_draw_color(*_C_BORDER)
    pdf.set_font(pdf._fn, "", 9)
    pdf.set_text_color(*_C_DARK)
    cleaned = _clean_text(summary)
    pdf.multi_cell(0, 5.5, cleaned, border=1, fill=True, padding=(3, 4, 3, 4))
    pdf.set_text_color(*_C_BLACK)


def _annotations_table(pdf: ArchonPDF, annotations: list[dict[str, Any]]) -> None:
    headers = ["Observación normativa", "Estado"]
    col_w = [148, 26]

    pdf.set_fill_color(*_C_HEADER_BG)
    pdf.set_text_color(*_C_WHITE)
    pdf.set_font(pdf._fn, "B", 8)
    for header, w in zip(headers, col_w, strict=True):
        pdf.cell(w, 7, f"  {header}", border=1, fill=True)
    pdf.ln()
    pdf.set_text_color(*_C_BLACK)

    for idx, ann in enumerate(annotations):
        status = ann.get("status", "info")
        description = _clean_text(ann.get("description", ""))
        if not description:
            continue

        color = _STATUS_COLOR.get(status, _C_INFO)
        label = _STATUS_SYMBOL.get(status, "INF")

        fill_color = _C_ROW_ALT if idx % 2 == 0 else _C_WHITE
        pdf.set_fill_color(*fill_color)
        pdf.set_font(pdf._fn, "", 8)

        line_height = 5.0
        lines = _wrap_text(description, col_w[0] - 6, pdf, pdf._fn, 8)
        row_h = max(line_height * len(lines), 7.0)

        x0 = pdf.get_x()
        y0 = pdf.get_y()

        if y0 + row_h > pdf.h - pdf.b_margin - 5:
            pdf.add_page()
            y0 = pdf.get_y()

        pdf.multi_cell(col_w[0], line_height, f"  {description}",
                       border="LRB", fill=True, max_line_height=line_height)
        y1 = pdf.get_y()
        actual_h = y1 - y0

        pdf.set_xy(x0 + col_w[0], y0)
        pdf.set_fill_color(*color)
        pdf.set_text_color(*_C_WHITE)
        pdf.set_font(pdf._fn, "B", 7)
        pdf.cell(col_w[1], actual_h, label, border=1, fill=True, align="C")
        pdf.set_fill_color(*fill_color)
        pdf.set_text_color(*_C_BLACK)
        pdf.ln()
        pdf.set_xy(x0, y1)


def _full_analysis_block(pdf: ArchonPDF, text: str) -> None:
    cleaned = _clean_text(text)
    paragraphs = [p.strip() for p in cleaned.split("\n") if p.strip()]

    for para in paragraphs:
        if para.startswith(("1.", "2.", "3.", "RESUMEN", "ANOTACIONES", "RECOMENDACIONES")):
            pdf.set_font(pdf._fn, "B", 9)
            pdf.set_text_color(*_C_ACCENT)
        else:
            pdf.set_font(pdf._fn, "", 8.5)
            pdf.set_text_color(*_C_BLACK)
        pdf.multi_cell(0, 5.2, para)
        pdf.ln(1)

    pdf.set_text_color(*_C_BLACK)


def _legend(pdf: ArchonPDF) -> None:
    pdf.set_font(pdf._fn, "B", 8)
    pdf.set_text_color(*_C_DARK)
    pdf.cell(0, 6, "Leyenda:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(pdf._fn, "", 8)
    items = [
        (_C_OK, "OK — Cumple la normativa"),
        (_C_WARN, "REV — Requiere revisión o verificación adicional"),
        (_C_ERR, "NOK — Posible incumplimiento detectado"),
        (_C_INFO, "INF — Información relevante"),
    ]
    for color, label in items:
        pdf.set_fill_color(*color)
        pdf.set_text_color(*_C_WHITE)
        pdf.cell(10, 5, _STATUS_SYMBOL[
            {_C_OK: "ok", _C_WARN: "warning", _C_ERR: "violation", _C_INFO: "info"}[color]
        ], fill=True, align="C")
        pdf.set_text_color(*_C_BLACK)
        pdf.cell(80, 5, f"  {_clean_text(label)}")
        pdf.ln(5)


def _clean_text(text: str) -> str:
    # Replace common Unicode punctuation with ASCII equivalents before encoding
    replacements = {
        "—": "-",   # em dash
        "–": "-",   # en dash
        "‘": "'",   # left single quote
        "’": "'",   # right single quote
        "“": '"',   # left double quote
        "”": '"',   # right double quote
        "…": "...", # ellipsis
        "•": "-",   # bullet
        "✓": "[OK]",    # checkmark
        "✔": "[OK]",    # heavy checkmark
        "✗": "[NOK]",   # ballot x
        "✘": "[NOK]",   # heavy ballot x
        "⚠": "[!]",     # warning sign
        "ℹ": "[i]",     # info
        "\ufe0f": "",    # emoji variation selector
        "✅": "[OK]",
        "❌": "[NOK]",
        "🔍": "[REV]",
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text.strip()


def _wrap_text(text: str, width_mm: float, pdf: FPDF, font: str, size: float) -> list[str]:
    pdf.set_font(font, "", size)
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if pdf.get_string_width(test) <= width_mm:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


# ── Expediente PDF (direct, no LLM roundtrip) ────────────────────────────────

def generate_expediente_pdf(expediente: Any, *, output_path: Path | None = None) -> Path:
    """
    Generate a professional compliance report PDF directly from an Expediente,
    using site_context and analysis_result already stored in the record.
    No LLM call required.
    """
    import json

    municipality = expediente.municipality or expediente.address or "Municipio desconocido"
    plan_name = Path(expediente.plan_path).name if expediente.plan_path else "Sin plano"

    # Parse stored JSON fields
    site_ctx: dict[str, Any] = {}
    if expediente.site_context:
        with suppress(json.JSONDecodeError, TypeError):
            site_ctx = json.loads(expediente.site_context)

    analysis: dict[str, Any] = {}
    if expediente.analysis_result:
        try:
            analysis = json.loads(expediente.analysis_result)
        except (json.JSONDecodeError, TypeError):
            # If stored as plain text, wrap it
            analysis = {
                "summary": expediente.analysis_result,
                "annotations": [],
                "full_analysis": expediente.analysis_result,
            }

    summary = analysis.get("summary", "Análisis pendiente.")
    verdict = str(analysis.get("verdict") or analysis.get("verdict_label") or "").strip()
    if verdict and verdict.lower() not in str(summary).lower()[:80]:
        summary = f"{verdict.upper()}\n\n{summary}"
    annotations = analysis.get("annotations", [])
    full_analysis = analysis.get("full_analysis", analysis.get("raw_analysis", ""))
    next_steps = analysis.get("next_steps") or []
    if not full_analysis and isinstance(next_steps, list) and next_steps:
        full_analysis = "Próximos pasos:\n" + "\n".join(f"- {step}" for step in next_steps)

    # Default output path: Desktop
    if output_path is None:
        stem = Path(expediente.plan_path).stem if expediente.plan_path else "expediente"
        safe_muni = municipality.lower().replace(" ", "_")[:30]
        from datetime import datetime as _dt
        ts = _dt.now().strftime("%Y%m%d_%H%M")
        output_path = Path.home() / "Desktop" / f"informe_{safe_muni}_{stem}_{ts}.pdf"

    pdf = ArchonPDF(municipality=municipality, plan_name=plan_name)
    pdf.add_page()

    # ── Cover: expediente metadata ────────────────────────────────────────
    pdf.set_font(pdf._fn, "B", 20)
    pdf.set_text_color(*_C_ACCENT)
    pdf.cell(0, 12, "INFORME DE CUMPLIMIENTO NORMATIVO", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(pdf._fn, "B", 13)
    pdf.set_text_color(*_C_DARK)
    pdf.cell(0, 8, _clean_text(expediente.title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    from datetime import datetime as _dt2
    try:
        dt = _dt2.fromisoformat(expediente.created_at)
        fecha_exp = dt.strftime("%d/%m/%Y")
    except (ValueError, AttributeError):
        fecha_exp = str(expediente.created_at or "")[:10]

    cover_rows = [
        ("Dirección", expediente.address or "-"),
        ("Municipio", municipality),
        ("Provincia", expediente.province or "-"),
        ("Ref. catastral", expediente.cadastral_ref or "-"),
        ("Plano analizado", plan_name),
        ("Fecha expediente", fecha_exp),
    ]
    if expediente.latitude and expediente.longitude:
        cover_rows.insert(
            4,
            ("Coordenadas GPS", f"{expediente.latitude:.6f}, {expediente.longitude:.6f}"),
        )

    col_w = [52, 120]
    for label, value in cover_rows:
        pdf.set_fill_color(*_C_LIGHT_BG)
        pdf.set_font(pdf._fn, "B", 9)
        pdf.cell(col_w[0], 7, f"  {label}", border=1, fill=True)
        pdf.set_font(pdf._fn, "", 9)
        pdf.set_fill_color(*_C_WHITE)
        pdf.cell(
            col_w[1],
            7,
            f"  {_clean_text(str(value))}",
            border=1,
            fill=True,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
    pdf.ln(6)

    # ── Parcel data from site_context ─────────────────────────────────────
    parcel = site_ctx.get("parcel_detail") or {}
    if isinstance(parcel, dict) and not parcel.get("error") and any(parcel.values()):
        _section_title(pdf, "DATOS OFICIALES DE PARCELA (CATASTRO)")
        parcel_rows = [
            ("Superficie m²", str(parcel.get("surface_m2") or "-")),
            ("Año construcción", str(parcel.get("construction_year") or "-")),
            ("Plantas sobre rasante", str(parcel.get("floors_above") or "-")),
            ("Plantas bajo rasante", str(parcel.get("floors_below") or "-")),
            ("Uso catastral", str(parcel.get("use_detail") or "-")),
        ]
        for label, value in parcel_rows:
            pdf.set_fill_color(*_C_LIGHT_BG)
            pdf.set_font(pdf._fn, "B", 9)
            pdf.cell(60, 6, f"  {label}", border=1, fill=True)
            pdf.set_font(pdf._fn, "", 9)
            pdf.set_fill_color(*_C_WHITE)
            pdf.cell(
                112,
                6,
                f"  {_clean_text(value)}",
                border=1,
                fill=True,
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )
        pdf.ln(5)

    # ── Legal checks panel ────────────────────────────────────────────────
    legal_checks: list[dict[str, Any]] = site_ctx.get("legal_checks", [])
    if legal_checks:
        _section_title(pdf, "PANEL DE VERIFICACION SECTORIAL")
        _legal_checks_table(pdf, legal_checks)
        pdf.ln(4)

    # ── Summary ───────────────────────────────────────────────────────────
    _section_title(pdf, "RESUMEN EJECUTIVO")
    _summary_box(pdf, summary if summary else "Análisis pendiente — ejecuta 'Analizar' primero.")
    pdf.ln(4)

    # ── Annotations table ─────────────────────────────────────────────────
    if annotations:
        _section_title(pdf, "TABLA DE VERIFICACION NORMATIVA")
        _annotations_table(pdf, annotations)
        pdf.ln(4)

    # ── Full analysis ─────────────────────────────────────────────────────
    if full_analysis:
        _section_title(pdf, "ANALISIS DETALLADO")
        _full_analysis_block(pdf, full_analysis)

    pdf.ln(4)
    _legend(pdf)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    return output_path


def _legal_checks_table(pdf: ArchonPDF, checks: list[dict[str, Any]]) -> None:
    _STATUS_CHECK_COLOR = {
        "ready": _C_OK,
        "conditional": _C_WARN,
        "pending_review": _C_INFO,
        "not_applicable": (160, 160, 160),
    }
    _STATUS_CHECK_LABEL = {
        "ready": "OK",
        "conditional": "REV",
        "pending_review": "PEN",
        "missing": "FAL",
        "not_applicable": "N/A",
    }
    headers = ["Verificación", "Estado", "Detalle"]
    col_w = [58, 18, 98]

    pdf.set_fill_color(*_C_HEADER_BG)
    pdf.set_text_color(*_C_WHITE)
    pdf.set_font(pdf._fn, "B", 8)
    for header, w in zip(headers, col_w, strict=True):
        pdf.cell(w, 7, f"  {header}", border=1, fill=True)
    pdf.ln()
    pdf.set_text_color(*_C_BLACK)

    for idx, check in enumerate(checks):
        name = _clean_text(
            str(
                check.get("title")
                or check.get("name")
                or check.get("check")
                or check.get("code")
                or ""
            )
        )
        status = str(check.get("status") or "pending_review")
        detail = _clean_text(str(check.get("detail") or check.get("description") or ""))

        color = _STATUS_CHECK_COLOR.get(status, _C_INFO)
        label = _STATUS_CHECK_LABEL.get(status, "?")

        fill_color = _C_ROW_ALT if idx % 2 == 0 else _C_WHITE
        pdf.set_fill_color(*fill_color)
        pdf.set_font(pdf._fn, "", 8)

        y0 = pdf.get_y()
        if y0 + 7 > pdf.h - pdf.b_margin - 5:
            pdf.add_page()
            y0 = pdf.get_y()

        pdf.cell(col_w[0], 7, f"  {name}", border=1, fill=True)

        pdf.set_fill_color(*color)
        pdf.set_text_color(*_C_WHITE)
        pdf.set_font(pdf._fn, "B", 7)
        pdf.cell(col_w[1], 7, label, border=1, fill=True, align="C")

        pdf.set_fill_color(*fill_color)
        pdf.set_text_color(*_C_BLACK)
        pdf.set_font(pdf._fn, "", 8)
        pdf.cell(col_w[2], 7, f"  {detail[:70]}", border=1, fill=True,
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
