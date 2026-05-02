from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF, XPos, YPos

# ── Font paths ────────────────────────────────────────────────────────────────
_DEJAVU_REGULAR = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
_DEJAVU_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")

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
        if _DEJAVU_REGULAR.exists():
            self.add_font("DejaVu", "", str(_DEJAVU_REGULAR))
        if _DEJAVU_BOLD.exists():
            self.add_font("DejaVu", "B", str(_DEJAVU_BOLD))
        self._fn = "DejaVu" if _DEJAVU_REGULAR.exists() else "Helvetica"

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


# ── Private helpers ───────────────────────────────────────────────────────────

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
