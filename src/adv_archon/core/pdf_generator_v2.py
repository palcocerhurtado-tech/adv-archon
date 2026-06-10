# mypy: ignore-errors
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fpdf.enums import XPos, YPos

from adv_archon.core import legal
from adv_archon.core.document_draft import DocumentDraft, DraftSection, DraftSource, DraftTable


def generate_draft_pdf(
    draft: DocumentDraft,
    output_path: Path,
    *,
    archon_logo_path: Path | None = None,
    client_logo_path: Path | None = None,
) -> Path:
    """Render an editable DocumentDraft into a professional preliminary PDF."""

    from fpdf import FPDF

    output_path = output_path.expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pdf = FPDF(unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    _brand_header(pdf, archon_logo_path=archon_logo_path, client_logo_path=client_logo_path)
    _title(pdf, draft)
    _metadata_table(pdf, draft)
    _notice(pdf)
    _section(pdf, "Resumen ejecutivo")
    _paragraph(pdf, draft.executive_summary or "Pendiente de completar.")

    for section in draft.sections:
        if section.include_in_report:
            _draft_section(pdf, section)
    for table in draft.tables:
        if table.include_in_report:
            _draft_table(pdf, table)
    if draft.sources:
        _sources(pdf, draft.sources)
    if draft.warnings:
        _section(pdf, "Advertencias")
        for warning in draft.warnings:
            _bullet(pdf, warning)
    if draft.next_steps:
        _section(pdf, "Próximos pasos")
        for index, step in enumerate(draft.next_steps, start=1):
            _paragraph(pdf, f"{index}. {step}")

    _legal_notice(pdf)
    _footer(pdf)
    pdf.output(str(output_path))
    return output_path


def _brand_header(
    pdf: object,
    *,
    archon_logo_path: Path | None,
    client_logo_path: Path | None,
) -> None:
    pdf.set_fill_color(5, 5, 5)  # type: ignore[attr-defined]
    pdf.rect(0, 0, 210, 20, "F")  # type: ignore[attr-defined]
    x = 14
    for logo in (archon_logo_path, client_logo_path):
        if logo and logo.exists():
            try:
                pdf.image(str(logo), x=x, y=4, w=12)  # type: ignore[attr-defined]
                x += 16
            except Exception:
                continue
    pdf.set_xy(x, 6)  # type: ignore[attr-defined]
    pdf.set_font("Helvetica", "B", 8)  # type: ignore[attr-defined]
    pdf.set_text_color(247, 247, 244)  # type: ignore[attr-defined]
    pdf.cell(
        0,
        6,
        _pdf_text("ADV ARCHON Studio Edition"),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )  # type: ignore[attr-defined]
    pdf.set_text_color(5, 5, 5)  # type: ignore[attr-defined]
    pdf.set_y(28)  # type: ignore[attr-defined]


def _title(pdf: object, draft: DocumentDraft) -> None:
    pdf.set_font("Helvetica", "B", 19)  # type: ignore[attr-defined]
    pdf.set_text_color(201, 162, 39)  # type: ignore[attr-defined]
    _reset_x(pdf)
    pdf.multi_cell(0, 8, _pdf_text(draft.title))  # type: ignore[attr-defined]
    pdf.set_font("Helvetica", "", 10)  # type: ignore[attr-defined]
    pdf.set_text_color(46, 46, 44)  # type: ignore[attr-defined]
    subtitle = "Informe preliminar de viabilidad urbanística"
    if draft.client_name:
        subtitle += f" · Preparado para: {draft.client_name}"
    _reset_x(pdf)
    pdf.multi_cell(0, 6, _pdf_text(subtitle))  # type: ignore[attr-defined]
    pdf.ln(4)  # type: ignore[attr-defined]


def _metadata_table(pdf: object, draft: DocumentDraft) -> None:
    rows = (
        ("Proyecto", draft.project_name),
        ("Municipio", draft.municipality),
        ("Referencia catastral", draft.cadastral_ref),
        ("Veredicto preliminar", draft.verdict),
        ("Fecha", datetime.now().strftime("%Y-%m-%d %H:%M")),
    )
    pdf.set_font("Helvetica", "B", 8)  # type: ignore[attr-defined]
    pdf.set_fill_color(46, 46, 44)  # type: ignore[attr-defined]
    pdf.set_text_color(247, 247, 244)  # type: ignore[attr-defined]
    pdf.cell(58, 7, "Campo", border=1, fill=True)  # type: ignore[attr-defined]
    pdf.cell(
        120,
        7,
        "Valor",
        border=1,
        fill=True,
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )  # type: ignore[attr-defined]
    pdf.set_font("Helvetica", "", 8)  # type: ignore[attr-defined]
    pdf.set_text_color(5, 5, 5)  # type: ignore[attr-defined]
    for key, value in rows:
        y = pdf.get_y()  # type: ignore[attr-defined]
        pdf.cell(58, 7, _pdf_text(key), border=1)  # type: ignore[attr-defined]
        pdf.multi_cell(120, 7, _pdf_text(value or "-"), border=1)  # type: ignore[attr-defined]
        if pdf.get_y() == y:  # type: ignore[attr-defined]
            pdf.ln(7)  # type: ignore[attr-defined]
    pdf.ln(5)  # type: ignore[attr-defined]


def _notice(pdf: object) -> None:
    pdf.set_fill_color(255, 248, 225)  # type: ignore[attr-defined]
    pdf.set_draw_color(201, 162, 39)  # type: ignore[attr-defined]
    pdf.set_font("Helvetica", "I", 8)  # type: ignore[attr-defined]
    _reset_x(pdf)
    pdf.multi_cell(
        0,
        6,
        _pdf_text(legal.document_short_disclaimer()),
        border=1,
        fill=True,
    )  # type: ignore[attr-defined]
    pdf.ln(5)  # type: ignore[attr-defined]


def _legal_notice(pdf: object) -> None:
    """Full legal/compliance block (RGPD, AI Act, professional liability)."""
    _section(pdf, "Aviso legal y de uso")
    pdf.set_font("Helvetica", "", 7)  # type: ignore[attr-defined]
    pdf.set_text_color(60, 60, 60)  # type: ignore[attr-defined]
    for block in legal.document_legal_footer().split("\n\n"):
        text = block.strip()
        if not text:
            continue
        _reset_x(pdf)
        pdf.multi_cell(0, 4.5, _pdf_text(text))  # type: ignore[attr-defined]
        pdf.ln(1)  # type: ignore[attr-defined]
    pdf.set_text_color(5, 5, 5)  # type: ignore[attr-defined]
    pdf.ln(3)  # type: ignore[attr-defined]


def _draft_section(pdf: object, section: DraftSection) -> None:
    _section(pdf, section.title)
    for block in section.content.split("\n\n"):
        if block.strip():
            _paragraph(pdf, block.strip())


def _draft_table(pdf: object, table: DraftTable) -> None:
    _section(pdf, table.title)
    columns = table.columns or ("Dato",)
    width = 178 / max(1, len(columns))
    pdf.set_font("Helvetica", "B", 7)  # type: ignore[attr-defined]
    pdf.set_fill_color(46, 46, 44)  # type: ignore[attr-defined]
    pdf.set_text_color(247, 247, 244)  # type: ignore[attr-defined]
    for column in columns:
        pdf.cell(width, 6, _pdf_text(column), border=1, fill=True)  # type: ignore[attr-defined]
    pdf.ln(6)  # type: ignore[attr-defined]
    pdf.set_font("Helvetica", "", 7)  # type: ignore[attr-defined]
    pdf.set_text_color(5, 5, 5)  # type: ignore[attr-defined]
    for row in table.rows:
        for idx in range(len(columns)):
            value = row[idx] if idx < len(row) else ""
            pdf.cell(width, 6, _pdf_text(value)[:42], border=1)  # type: ignore[attr-defined]
        pdf.ln(6)  # type: ignore[attr-defined]
    pdf.ln(3)  # type: ignore[attr-defined]


def _sources(pdf: object, sources: tuple[DraftSource, ...]) -> None:
    _section(pdf, "Fuentes y trazabilidad")
    for source in sources:
        label = "Dato oficial" if source.official else "Inferencia / apoyo"
        _bullet(
            pdf,
            f"{source.title} ({label}) · {source.result or source.reference or source.url}",
        )


def _section(pdf: object, title: str) -> None:
    pdf.set_font("Helvetica", "B", 11)  # type: ignore[attr-defined]
    pdf.set_text_color(201, 162, 39)  # type: ignore[attr-defined]
    _reset_x(pdf)
    pdf.cell(
        0,
        8,
        _pdf_text(title),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )  # type: ignore[attr-defined]
    pdf.set_draw_color(201, 162, 39)  # type: ignore[attr-defined]
    y = pdf.get_y()  # type: ignore[attr-defined]
    pdf.line(10, y, 200, y)  # type: ignore[attr-defined]
    pdf.ln(3)  # type: ignore[attr-defined]
    pdf.set_text_color(5, 5, 5)  # type: ignore[attr-defined]


def _paragraph(pdf: object, text: str) -> None:
    pdf.set_font("Helvetica", "", 9)  # type: ignore[attr-defined]
    pdf.set_text_color(46, 46, 44)  # type: ignore[attr-defined]
    _reset_x(pdf)
    pdf.multi_cell(0, 5.2, _pdf_text(text))  # type: ignore[attr-defined]
    pdf.ln(1)  # type: ignore[attr-defined]


def _bullet(pdf: object, text: str) -> None:
    _paragraph(pdf, f"- {text}")


def _footer(pdf: object) -> None:
    page_count = pdf.page_no()  # type: ignore[attr-defined]
    for page in range(1, page_count + 1):
        pdf.page = page  # type: ignore[attr-defined]
        pdf.set_y(-12)  # type: ignore[attr-defined]
        pdf.set_font("Helvetica", "", 7)  # type: ignore[attr-defined]
        pdf.set_text_color(130, 130, 126)  # type: ignore[attr-defined]
        pdf.cell(
            0,
            5,
            _pdf_text(f"Generado por ADV ARCHON · Página {page}"),
            align="C",
        )  # type: ignore[attr-defined]


def _pdf_text(value: object) -> str:
    return str(value).replace("–", "-").replace("—", "-").encode(
        "latin-1",
        errors="replace",
    ).decode("latin-1")


def _reset_x(pdf: object) -> None:
    pdf.set_x(10)  # type: ignore[attr-defined]
