"""Exportación del Presupuesto de Ejecución Material (PEM) a PDF profesional con fpdf2."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fpdf import FPDF, XPos, YPos

from adv_archon.tools.pem import PEMResult, calcular_pem

if TYPE_CHECKING:
    pass

# ── Fonts ─────────────────────────────────────────────────────────────────────
_REGULAR = [
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]
_BOLD = [
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]

# ── Palette ───────────────────────────────────────────────────────────────────
_NAVY = (28, 54, 102)
_ACCENT = (40, 80, 160)
_LIGHT = (244, 246, 252)
_BORDER = (200, 208, 228)
_GRAY = (110, 110, 120)
_BLACK = (28, 28, 36)
_WHITE = (255, 255, 255)
_SECTION_BG = (234, 238, 250)
_AMBER_BG = (255, 248, 230)
_AMBER_BORDER = (220, 160, 0)
_AMBER_TEXT = (100, 70, 0)


class _PEMPDF(FPDF):
    def __init__(self, despacho: str, title: str) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self._despacho = despacho or "ADV ARCHON"
        self._title = title[:60]
        self.set_margins(20, 20, 20)
        self.set_auto_page_break(auto=True, margin=24)

        regular = next((p for p in _REGULAR if p.exists()), None)
        bold = next((p for p in _BOLD if p.exists()), regular)
        if regular:
            self.add_font("M", "", str(regular))
            self.add_font("M", "B", str(bold or regular))
            self._fn = "M"
        else:
            self._fn = "Helvetica"

    def header(self) -> None:
        self.set_fill_color(*_NAVY)
        self.rect(0, 0, 210, 13, style="F")
        self.set_y(1.5)
        self.set_font(self._fn, "B", 8)
        self.set_text_color(*_WHITE)
        self.cell(0, 10, f"{self._despacho}  ·  PRESUPUESTO DE EJECUCIÓN MATERIAL", align="C")
        self.set_text_color(*_BLACK)
        self.ln(6)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_draw_color(*_BORDER)
        self.line(20, self.get_y(), 190, self.get_y())
        self.ln(1)
        self.set_font(self._fn, "", 7)
        self.set_text_color(*_GRAY)
        self.cell(
            0,
            7,
            "Generado por ADV ARCHON  ·  Baremos orientativos COA 2024  ·  No vinculante"
            f"  ·  Pág. {self.page_no()}",
            align="C",
        )
        self.set_text_color(*_BLACK)


def _cover_band(pdf: _PEMPDF, title: str, despacho: str, generated_at: str) -> None:
    """Render the navy cover/header band with title."""
    pdf.set_fill_color(*_NAVY)
    pdf.rect(0, 35, 210, 40, style="F")
    pdf.set_y(42)
    pdf.set_font(pdf._fn, "B", 20)
    pdf.set_text_color(*_WHITE)
    pdf.cell(
        0, 12, "PRESUPUESTO DE EJECUCIÓN MATERIAL",
        align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    pdf.set_font(pdf._fn, "", 11)
    pdf.cell(0, 8, title, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_BLACK)

    pdf.set_y(90)
    pdf.set_font(pdf._fn, "", 9)
    pdf.set_text_color(*_GRAY)
    pdf.cell(0, 6, f"Despacho: {despacho}", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, f"Generado el {generated_at}", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_BLACK)


def _data_table(pdf: _PEMPDF, result: PEMResult) -> None:
    """Render the input data table: tipología, calidad, zona, superficie, módulos."""
    pdf.ln(6)
    # Section heading
    pdf.set_fill_color(*_SECTION_BG)
    pdf.set_draw_color(*_ACCENT)
    pdf.set_font(pdf._fn, "B", 10)
    pdf.set_text_color(*_ACCENT)
    pdf.set_line_width(0.4)
    pdf.rect(20, pdf.get_y(), 170, 8, style="DF")
    pdf.cell(170, 8, "  DATOS DE ENTRADA", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_BLACK)
    pdf.set_line_width(0.2)
    pdf.ln(1)

    col_label = 70
    col_value = 100
    rows = [
        ("Tipología", result.tipologia.replace("_", " ").title()),
        ("Calidad", result.calidad.title()),
        ("Zona geográfica", result.zona.replace("_", " ").title()),
        ("Superficie construida", f"{result.superficie_construida_m2:,.0f} m²"),
        ("Superficie sótano", f"{result.superficie_sótano_m2:,.0f} m²"),
        ("Módulo base", f"{result.modulo_base_eur_m2:,.0f} €/m²"),
        ("Factor zona", f"× {result.factor_zona:.2f}"),
        ("Módulo final aplicado", f"{result.modulo_final_eur_m2:,.0f} €/m²"),
    ]
    for label, value in rows:
        pdf.set_font(pdf._fn, "B", 9)
        pdf.set_fill_color(*_LIGHT)
        pdf.cell(col_label, 8, f"  {label}", border=1, fill=True,
                 new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font(pdf._fn, "", 9)
        pdf.set_fill_color(*_WHITE)
        pdf.cell(col_value, 8, f"  {value}", border=1, fill=True,
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _results_table(pdf: _PEMPDF, result: PEMResult) -> None:
    """Render the results table with PEM, fees, PEC, and IVA."""
    pdf.ln(6)
    # Section heading
    pdf.set_fill_color(*_SECTION_BG)
    pdf.set_draw_color(*_ACCENT)
    pdf.set_font(pdf._fn, "B", 10)
    pdf.set_text_color(*_ACCENT)
    pdf.set_line_width(0.4)
    pdf.rect(20, pdf.get_y(), 170, 8, style="DF")
    pdf.cell(170, 8, "  RESULTADOS ECONÓMICOS", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_BLACK)
    pdf.set_line_width(0.2)
    pdf.ln(1)

    sup = result.superficie_construida_m2 or 1.0  # avoid division by zero
    col_concepto = 90
    col_eur_m2 = 40
    col_total = 40

    # Header row
    pdf.set_font(pdf._fn, "B", 8.5)
    pdf.set_fill_color(*_NAVY)
    pdf.set_text_color(*_WHITE)
    pdf.cell(col_concepto, 8, "  Concepto", border=1, fill=True,
             new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(col_eur_m2, 8, "€/m²", border=1, fill=True, align="R",
             new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(col_total, 8, "Total (€)", border=1, fill=True, align="R",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_BLACK)

    hon_pct_label = f"Honorarios técnicos ({result.honorarios_pct * 100:.1f}% PEM)"

    rows = [
        ("PEM (Presupuesto de Ejecución Material)",
         result.pem_eur / sup, result.pem_eur),
        ("PEM + GG/BI (× 1.13)",
         result.pem_con_beneficio_industrial_eur / sup,
         result.pem_con_beneficio_industrial_eur),
        (hon_pct_label,
         result.honorarios_tecnicos_eur / sup,
         result.honorarios_tecnicos_eur),
        ("Licencia de obras – ICIO (~ 4% PEM)",
         result.licencia_obras_eur / sup,
         result.licencia_obras_eur),
        ("PEC total sin IVA",
         result.pec_sin_iva_eur / sup,
         result.pec_sin_iva_eur),
        ("PEC total con IVA (21%)",
         result.pec_con_iva_eur / sup,
         result.pec_con_iva_eur),
    ]

    for i, (concepto, eur_m2, total) in enumerate(rows):
        is_highlight = any(h in concepto for h in ("PEC total", "PEM (Pres"))
        fill_color = _LIGHT if i % 2 == 0 else _WHITE
        if is_highlight:
            fill_color = _SECTION_BG

        pdf.set_font(pdf._fn, "B" if is_highlight else "", 9)
        pdf.set_fill_color(*fill_color)
        pdf.cell(col_concepto, 8, f"  {concepto}", border=1, fill=True,
                 new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font(pdf._fn, "", 9)
        pdf.cell(col_eur_m2, 8, f"{eur_m2:,.0f} €", border=1, fill=True, align="R",
                 new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font(pdf._fn, "B" if is_highlight else "", 9)
        pdf.cell(col_total, 8, f"{total:,.0f} €", border=1, fill=True, align="R",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _disclaimer_box(pdf: _PEMPDF) -> None:
    """Render the amber legal disclaimer box."""
    pdf.ln(6)
    pdf.set_fill_color(*_AMBER_BG)
    pdf.set_draw_color(*_AMBER_BORDER)
    pdf.rect(20, pdf.get_y(), 170, 20, style="DF")
    pdf.set_font(pdf._fn, "", 7.5)
    pdf.set_text_color(*_AMBER_TEXT)
    pdf.set_xy(22, pdf.get_y() + 2)
    pdf.multi_cell(
        166,
        4.5,
        "AVISO: Este presupuesto ha sido generado automáticamente por ADV ARCHON con base en los "
        "baremos orientativos de los Colegios de Arquitectos de España (COA 2024). Los valores son "
        "estimaciones de referencia y no constituyen oferta económica, presupuesto contractual ni "
        "documento técnico oficial. Los importes reales pueden variar en función del proyecto, "
        "contratista, zona y condiciones de mercado. No vinculante.",
    )
    pdf.set_text_color(*_BLACK)


def generate_pem_pdf(
    result: PEMResult,
    output_path: Path,
    *,
    despacho: str,
    title: str,
) -> Path:
    """Render a PEM result as a professional PDF.

    Returns the saved path.
    """
    generated_at = datetime.now(UTC).strftime("%d/%m/%Y %H:%M")
    despacho_name = despacho or "ADV ARCHON"
    doc_title = title or "Presupuesto de Ejecución Material"

    pdf = _PEMPDF(despacho_name, doc_title)
    pdf.add_page()

    _cover_band(pdf, doc_title, despacho_name, generated_at)
    _data_table(pdf, result)
    _results_table(pdf, result)
    _disclaimer_box(pdf)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    return output_path


# ── Tool wrapper ──────────────────────────────────────────────────────────────

class PEMPDFTools:
    def __init__(self) -> None:
        self._exp_store: Any = None

    def set_expediente_store(self, store: Any) -> None:
        self._exp_store = store

    def exportar_pem_pdf(
        self,
        superficie_construida_m2: float,
        tipologia: str = "residencial_unifamiliar",
        calidad: str = "media",
        zona: str = "nacional",
        num_plantas: int = 1,
        superficie_sotano_m2: float = 0.0,
        despacho: str = "",
        guardar_en: str = "",
    ) -> dict[str, Any]:
        """Calculate PEM and export results as a professional PDF."""
        try:
            result = calcular_pem(
                superficie_construida_m2=superficie_construida_m2,
                tipologia=tipologia,
                calidad=calidad,
                zona=zona,
                num_plantas=num_plantas,
                superficie_sótano_m2=superficie_sotano_m2,
            )
        except Exception as exc:
            return {"ok": False, "error": f"Error calculando PEM: {exc}"}

        tip_safe = tipologia[:20].replace(" ", "_")
        sup_int = int(superficie_construida_m2)
        default_out = Path.home() / "Desktop" / f"PEM_{tip_safe}_{sup_int}m2.pdf"
        out = Path(guardar_en).expanduser() if guardar_en else default_out
        doc_title = f"{tipologia.replace('_', ' ').title()} · {superficie_construida_m2:,.0f} m²"

        try:
            generate_pem_pdf(result, out, despacho=despacho, title=doc_title)
        except Exception as exc:
            return {"ok": False, "error": f"Error renderizando PDF: {exc}"}

        return {
            "ok": True,
            "pdf": str(out),
            "resumen": {
                "PEM": f"{result.pem_eur:,.0f} €",
                "PEM + GG/BI": f"{result.pem_con_beneficio_industrial_eur:,.0f} €",
                f"Honorarios técnicos ({result.honorarios_pct * 100:.1f}%)": (
                    f"{result.honorarios_tecnicos_eur:,.0f} €"
                ),
                "Licencia obras (ICIO)": f"{result.licencia_obras_eur:,.0f} €",
                "PEC sin IVA": f"{result.pec_sin_iva_eur:,.0f} €",
                "PEC con IVA (21%)": f"{result.pec_con_iva_eur:,.0f} €",
            },
        }
