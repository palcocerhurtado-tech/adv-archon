"""Exportación de la Memoria Descriptiva a PDF profesional con fpdf2."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fpdf import FPDF, XPos, YPos

if TYPE_CHECKING:
    from adv_archon.core.expediente import Expediente
    from adv_archon.core.knowledge import KnowledgeStore
    from adv_archon.core.llm import LLMRouter

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


class _MemoriaPDF(FPDF):
    def __init__(
        self,
        expediente_title: str,
        despacho: str,
        logo_path: Path | None = None,
    ) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self._exp_title = expediente_title[:60]
        self._despacho = despacho or "ADV ARCHON"
        self._logo_path = logo_path
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
        # Banda superior
        self.set_fill_color(*_NAVY)
        self.rect(0, 0, 210, 13, style="F")
        self.set_y(1.5)
        self.set_font(self._fn, "B", 8)
        self.set_text_color(*_WHITE)

        # Logo si existe
        if self._logo_path and self._logo_path.exists():
            from contextlib import suppress
            with suppress(Exception):
                self.image(str(self._logo_path), x=3, y=1.5, h=10)

        self.cell(0, 10, f"{self._despacho}  ·  MEMORIA DESCRIPTIVA", align="C")
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
            0, 7,
            f"{self._exp_title}  ·  Generado por ADV ARCHON  ·  "
            f"Análisis preliminar no vinculante  ·  Pág. {self.page_no()}",
            align="C",
        )
        self.set_text_color(*_BLACK)


def _section_heading(pdf: _MemoriaPDF, title: str) -> None:
    pdf.ln(3)
    pdf.set_fill_color(*_SECTION_BG)
    pdf.set_draw_color(*_ACCENT)
    pdf.set_font(pdf._fn, "B", 10)
    pdf.set_text_color(*_ACCENT)
    pdf.set_line_width(0.4)
    pdf.rect(20, pdf.get_y(), 170, 8, style="DF")
    pdf.cell(170, 8, f"  {title}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_BLACK)
    pdf.set_line_width(0.2)
    pdf.ln(1)


def _body_text(pdf: _MemoriaPDF, text: str) -> None:
    pdf.set_font(pdf._fn, "", 9.5)
    pdf.set_text_color(*_BLACK)
    pdf.multi_cell(0, 5.5, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)


def _cover_page(
    pdf: _MemoriaPDF,
    expediente: Expediente,
    despacho: str,
    generated_at: str,
) -> None:
    pdf.add_page()

    # Banda de título
    pdf.set_fill_color(*_NAVY)
    pdf.rect(0, 35, 210, 45, style="F")
    pdf.set_y(42)
    pdf.set_font(pdf._fn, "B", 22)
    pdf.set_text_color(*_WHITE)
    pdf.cell(0, 12, "MEMORIA DESCRIPTIVA", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(pdf._fn, "", 13)
    title = expediente.title[:55] + ("…" if len(expediente.title) > 55 else "")
    pdf.cell(0, 9, title, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(pdf._fn, "", 10)
    pdf.cell(0, 8, f"{expediente.municipality} ({expediente.province})",
             align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_BLACK)

    # Tabla de datos clave
    pdf.set_y(100)
    rows = [
        ("Dirección", expediente.address or "—"),
        ("Municipio / Provincia", f"{expediente.municipality} / {expediente.province}"),
        ("Ref. Catastral", expediente.cadastral_ref or "Pendiente"),
        ("Estado del expediente", expediente.status or "—"),
        ("Coordenadas", (
            f"{expediente.latitude:.6f}, {expediente.longitude:.6f}"
            if expediente.latitude else "No disponibles"
        )),
    ]
    pdf.set_font(pdf._fn, "B", 9)
    pdf.set_fill_color(*_LIGHT)
    col_w = (55, 115)
    for label, value in rows:
        pdf.set_font(pdf._fn, "B", 9)
        pdf.set_fill_color(*_LIGHT)
        pdf.cell(col_w[0], 8, f"  {label}", border=1, fill=True,
                 new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font(pdf._fn, "", 9)
        pdf.set_fill_color(*_WHITE)
        pdf.cell(col_w[1], 8, f"  {value}", border=1, fill=True,
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Despacho y fecha
    pdf.ln(10)
    pdf.set_font(pdf._fn, "", 9)
    pdf.set_text_color(*_GRAY)
    pdf.cell(0, 6, f"Despacho: {despacho}", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, f"Generado el {generated_at}", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_BLACK)

    # Aviso legal
    pdf.set_y(-50)
    pdf.set_fill_color(255, 248, 230)
    pdf.set_draw_color(220, 160, 0)
    pdf.rect(20, pdf.get_y(), 170, 16, style="DF")
    pdf.set_font(pdf._fn, "", 7.5)
    pdf.set_text_color(100, 70, 0)
    pdf.set_xy(22, pdf.get_y() + 2)
    pdf.multi_cell(166, 4.5,
        "AVISO: Este documento ha sido generado automáticamente por ADV ARCHON como apoyo "
        "al trabajo del profesional. No constituye un documento técnico oficial ni sustituye "
        "la firma y responsabilidad del arquitecto competente.",
    )
    pdf.set_text_color(*_BLACK)


def _parse_sections(text: str) -> list[tuple[str, str]]:
    """Split memoria text into (section_title, body) pairs."""
    import re
    pattern = re.compile(
        r"^(\d+\.\s+[A-ZÁÉÍÓÚÜÑ][^\n]{3,80})$",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(text))
    if not matches:
        return [("CONTENIDO", text.strip())]
    sections: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end():end].strip()
        sections.append((m.group(1).strip(), body))
    preamble = text[:matches[0].start()].strip()
    if preamble:
        sections.insert(0, ("INTRODUCCIÓN", preamble))
    return sections


def generate_memoria_pdf(
    texto: str,
    expediente: Expediente,
    output_path: Path,
    *,
    despacho: str = "",
    logo_path: Path | None = None,
) -> Path:
    """Render a memoria descriptiva text as a professional PDF.

    Returns the saved path.
    """
    generated_at = datetime.now(UTC).strftime("%d/%m/%Y %H:%M")
    despacho_name = despacho or "ADV ARCHON"

    pdf = _MemoriaPDF(expediente.title, despacho_name, logo_path)
    _cover_page(pdf, expediente, despacho_name, generated_at)

    # Content pages
    pdf.add_page()
    sections = _parse_sections(texto)
    for title, body in sections:
        if pdf.get_y() > 240:
            pdf.add_page()
        _section_heading(pdf, title)
        if body:
            _body_text(pdf, body)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    return output_path


# ── Tool wrapper ──────────────────────────────────────────────────────────────

class MemoriaPDFTools:
    def __init__(self, llm: LLMRouter, knowledge_store: KnowledgeStore | None = None) -> None:
        self._llm = llm
        self._ks = knowledge_store
        self._exp_store: Any = None

    def set_expediente_store(self, store: Any) -> None:
        self._exp_store = store

    def exportar_memoria_pdf(
        self,
        expediente_id: str,
        despacho: str = "",
        logo_path: str = "",
        guardar_en: str = "",
    ) -> dict[str, Any]:
        """Generate a memoria descriptiva and export it directly as a PDF."""
        from adv_archon.core.memoria_descriptiva import generar_memoria_descriptiva

        if self._exp_store is None:
            return {"ok": False, "error": "No hay ExpedienteStore configurado."}

        exp = self._exp_store.get(expediente_id)
        if exp is None:
            return {"ok": False, "error": f"Expediente {expediente_id!r} no encontrado."}

        try:
            texto = generar_memoria_descriptiva(exp, self._llm, knowledge_store=self._ks)
        except Exception as exc:
            return {"ok": False, "error": f"Error generando memoria: {exc}"}

        safe = exp.title[:40].replace(" ", "_")
        default_out = Path.home() / "Desktop" / f"Memoria_{safe}.pdf"
        out = Path(guardar_en).expanduser() if guardar_en else default_out
        logo = Path(logo_path).expanduser() if logo_path else None

        try:
            generate_memoria_pdf(texto, exp, out, despacho=despacho, logo_path=logo)
        except Exception as exc:
            return {"ok": False, "error": f"Error renderizando PDF: {exc}"}

        return {
            "ok": True,
            "expediente": exp.title,
            "pdf": str(out),
            "paginas": "generado",
        }
