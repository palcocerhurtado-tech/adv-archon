"""Informe de Proyecto Integrado — PDF único con portada, edificabilidad,
PEM y Memoria Descriptiva completa, generado desde un expediente.
"""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fpdf import FPDF, XPos, YPos

if TYPE_CHECKING:
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

# ── Palette (Archon brand) ────────────────────────────────────────────────────
_NAVY      = (28,  54, 102)
_GOLD      = (180, 140,  30)
_ACCENT    = (40,  80, 160)
_LIGHT     = (244, 246, 252)
_BORDER    = (200, 208, 228)
_GRAY      = (110, 110, 120)
_BLACK     = (28,  28,  36)
_WHITE     = (255, 255, 255)
_SEC_BG    = (234, 238, 250)
_ROW_ALT   = (248, 249, 254)
_OK        = (50, 140,  60)
_WARN      = (190, 120,   0)
_ERR       = (180,  40,  40)


class _InformePDF(FPDF):
    def __init__(self, expediente_title: str, despacho: str, logo_path: Path | None) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self._exp_title = expediente_title[:55]
        self._despacho  = despacho or "ADV ARCHON"
        self._logo      = logo_path
        self.set_margins(20, 20, 20)
        self.set_auto_page_break(auto=True, margin=26)
        regular = next((p for p in _REGULAR if p.exists()), None)
        bold    = next((p for p in _BOLD    if p.exists()), regular)
        if regular:
            self.add_font("F", "",  str(regular))
            self.add_font("F", "B", str(bold or regular))
            self._fn = "F"
        else:
            self._fn = "Helvetica"

    def header(self) -> None:
        self.set_fill_color(*_NAVY)
        self.rect(0, 0, 210, 13, style="F")
        self.set_y(1.5)
        self.set_font(self._fn, "B", 8)
        self.set_text_color(*_WHITE)
        if self._logo and self._logo.exists():
            with suppress(Exception):
                self.image(str(self._logo), x=3, y=2, h=9)
        self.cell(0, 10, f"{self._despacho}  ·  INFORME DE PROYECTO", align="C")
        self.set_text_color(*_BLACK)
        self.ln(5)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_draw_color(*_BORDER)
        self.line(20, self.get_y(), 190, self.get_y())
        self.ln(1)
        self.set_font(self._fn, "", 7)
        self.set_text_color(*_GRAY)
        self.cell(
            0, 7,
            f"{self._exp_title}  ·  ADV ARCHON  ·  "
            f"Análisis preliminar no vinculante  ·  Pág. {self.page_no()}",
            align="C",
        )
        self.set_text_color(*_BLACK)


# ── Layout helpers ─────────────────────────────────────────────────────────────

def _section(pdf: _InformePDF, title: str) -> None:
    pdf.ln(4)
    pdf.set_fill_color(*_SEC_BG)
    pdf.set_draw_color(*_ACCENT)
    pdf.set_line_width(0.4)
    pdf.set_font(pdf._fn, "B", 10)
    pdf.set_text_color(*_ACCENT)
    pdf.rect(20, pdf.get_y(), 170, 8, style="DF")
    pdf.cell(170, 8, f"  {title}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_BLACK)
    pdf.set_line_width(0.2)
    pdf.ln(1)


def _kv_table(pdf: _InformePDF, rows: list[tuple[str, str]]) -> None:
    col = (60, 110)
    alt = False
    for label, value in rows:
        pdf.set_fill_color(*(_ROW_ALT if alt else _WHITE))
        pdf.set_font(pdf._fn, "B", 9)
        pdf.cell(col[0], 7, f"  {label}", border=1, fill=True,
                 new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font(pdf._fn, "", 9)
        pdf.cell(col[1], 7, f"  {value}", border=1, fill=True,
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        alt = not alt
    pdf.ln(2)


def _numeric_table(pdf: _InformePDF, rows: list[dict[str, Any]], cols: tuple[str, ...]) -> None:
    widths = (80, 55, 35)
    pdf.set_fill_color(*_NAVY)
    pdf.set_font(pdf._fn, "B", 8.5)
    pdf.set_text_color(*_WHITE)
    for col, w in zip(cols, widths, strict=True):
        pdf.cell(w, 7, f"  {col}", border=0, fill=True,
                 new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln(7)
    pdf.set_text_color(*_BLACK)
    alt = False
    for row in rows:
        pdf.set_fill_color(*(_ROW_ALT if alt else _WHITE))
        pdf.set_font(pdf._fn, "", 8.5)
        vals = [str(row.get(k, "")) for k in ("concepto", "valor", "unidad")]
        for val, w in zip(vals, widths, strict=True):
            pdf.cell(w, 6.5, f"  {val}", border="B", fill=True,
                     new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.ln(6.5)
        alt = not alt
    pdf.ln(2)


def _body(pdf: _InformePDF, text: str) -> None:
    pdf.set_font(pdf._fn, "", 9.5)
    pdf.set_text_color(*_BLACK)
    pdf.multi_cell(0, 5.5, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)


# ── Cover ──────────────────────────────────────────────────────────────────────

def _cover(pdf: _InformePDF, exp: Any, despacho: str, generated_at: str) -> None:
    pdf.add_page()
    # Title band
    pdf.set_fill_color(*_NAVY)
    pdf.rect(0, 32, 210, 52, style="F")
    pdf.set_y(38)
    pdf.set_font(pdf._fn, "B", 24)
    pdf.set_text_color(*_WHITE)
    pdf.cell(0, 13, "INFORME DE PROYECTO", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(pdf._fn, "B", 13)
    title = exp.title[:52] + ("…" if len(exp.title) > 52 else "")
    pdf.cell(0, 9, title, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(pdf._fn, "", 10)
    pdf.cell(0, 8, f"{exp.municipality}  ·  {exp.province}",
             align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_BLACK)

    # Data table
    pdf.set_y(100)
    coords = (
        f"{exp.latitude:.6f}, {exp.longitude:.6f}" if exp.latitude else "No disponibles"
    )
    _kv_table(pdf, [
        ("Dirección",          exp.address or "—"),
        ("Municipio",          f"{exp.municipality} ({exp.province})"),
        ("Ref. Catastral",     exp.cadastral_ref or "Pendiente"),
        ("Coordenadas",        coords),
        ("Estado",             exp.status or "—"),
        ("Creado",             exp.created_at[:10] if exp.created_at else "—"),
    ])

    # Footer info
    pdf.set_y(-60)
    pdf.set_font(pdf._fn, "", 9)
    pdf.set_text_color(*_GRAY)
    pdf.cell(0, 7, f"Despacho: {despacho}", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 7, f"Generado el {generated_at}", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_BLACK)

    # Disclaimer
    pdf.set_y(-38)
    pdf.set_fill_color(255, 248, 230)
    pdf.set_draw_color(220, 160, 0)
    pdf.rect(20, pdf.get_y(), 170, 18, style="DF")
    pdf.set_font(pdf._fn, "", 7.5)
    pdf.set_text_color(100, 70, 0)
    pdf.set_xy(22, pdf.get_y() + 3)
    pdf.multi_cell(166, 4.5,
        "AVISO: Informe generado automáticamente por ADV ARCHON como apoyo al trabajo "
        "del profesional. No constituye documento técnico oficial ni sustituye la firma "
        "y responsabilidad del arquitecto colegiado competente.",
    )
    pdf.set_text_color(*_BLACK)


# ── Section parsers ────────────────────────────────────────────────────────────

def _parse_memoria_sections(text: str) -> list[tuple[str, str]]:
    import re
    pattern = re.compile(r"^(\d+\.\s+[A-ZÁÉÍÓÚÜÑ][^\n]{3,80})$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    if not matches:
        return [("CONTENIDO", text.strip())]
    sections: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end():end].strip()
        sections.append((m.group(1).strip(), body))
    pre = text[:matches[0].start()].strip()
    if pre:
        sections.insert(0, ("INTRODUCCIÓN", pre))
    return sections


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_informe_proyecto(
    *,
    expediente: Any,
    output_path: Path,
    despacho: str = "",
    logo_path: Path | None = None,
    edificabilidad_result: Any | None = None,
    pem_result: Any | None = None,
    memoria_text: str = "",
    energia_result: dict[str, Any] | None = None,
) -> Path:
    """Render the full project report as a professional PDF.

    Sections included depending on available data:
      Cover → Datos del proyecto → Edificabilidad (opt) → PEM (opt)
             → Energía (opt) → Memoria Descriptiva (opt)
    """
    generated_at = datetime.now(UTC).strftime("%d/%m/%Y %H:%M")
    despacho_name = despacho or "ADV ARCHON"

    pdf = _InformePDF(expediente.title, despacho_name, logo_path)
    _cover(pdf, expediente, despacho_name, generated_at)

    # ── 1. Edificabilidad ──────────────────────────────────────────────────────
    if edificabilidad_result is not None:
        pdf.add_page()
        _section(pdf, "1. PARÁMETROS URBANÍSTICOS Y EDIFICABILIDAD")
        rows = [
            {"concepto": d["parametro"], "valor": d["valor"], "unidad": d["unidad"]}
            for d in edificabilidad_result.get("tabla", [])
        ]
        if rows:
            _numeric_table(pdf, rows, ("Parámetro", "Valor", "Unidad"))

    # ── 2. PEM ─────────────────────────────────────────────────────────────────
    if pem_result is not None:
        if not edificabilidad_result:
            pdf.add_page()
        else:
            if pdf.get_y() > 180:
                pdf.add_page()
        _section(pdf, "2. PRESUPUESTO DE EJECUCIÓN MATERIAL (PEM)")
        resumen = pem_result.get("resumen", {})
        if resumen:
            _kv_table(pdf, [(k, v) for k, v in resumen.items()])
        rows = pem_result.get("desglose", [])
        if rows:
            _numeric_table(
                pdf,
                [{"concepto": r["concepto"], "valor": r["valor"], "unidad": r["unidad"]}
                 for r in rows],
                ("Concepto", "Valor", "Unidad"),
            )

    # ── 3. Energía ─────────────────────────────────────────────────────────────
    if energia_result and energia_result.get("ok"):
        if pdf.get_y() > 180:
            pdf.add_page()
        _section(pdf, "3. PRE-ANÁLISIS ENERGÉTICO (CTE DB-HE)")
        zona = energia_result.get("zona_climatica", "—")
        _kv_table(pdf, [
            ("Zona climática CTE",    zona),
            ("Municipio",             energia_result.get("municipio", "—")),
            ("Severidad de invierno", energia_result.get("severidad_invierno", "—")),
            ("Severidad de verano",   energia_result.get("severidad_verano", "—")),
        ])
        trans = energia_result.get("transmitancias_maximas", {})
        if trans:
            _numeric_table(pdf,
                [{"concepto": k, "valor": v, "unidad": "W/m²K"} for k, v in trans.items()],
                ("Elemento", "U máx. (W/m²K)", ""),
            )

    # ── 4. Memoria Descriptiva ─────────────────────────────────────────────────
    if memoria_text.strip():
        pdf.add_page()
        _section(pdf, "4. MEMORIA DESCRIPTIVA")
        for title, body in _parse_memoria_sections(memoria_text):
            if pdf.get_y() > 245:
                pdf.add_page()
            pdf.set_font(pdf._fn, "B", 9.5)
            pdf.set_text_color(*_NAVY)
            pdf.cell(0, 6, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(*_BLACK)
            if body:
                _body(pdf, body)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    return output_path


# ── Tool wrapper ───────────────────────────────────────────────────────────────

class InformeProyectoTools:
    def __init__(self, llm: LLMRouter, knowledge_store: KnowledgeStore | None = None) -> None:
        self._llm = llm
        self._ks  = knowledge_store
        self._exp_store: Any = None

    def set_expediente_store(self, store: Any) -> None:
        self._exp_store = store

    def generar_informe_proyecto(  # noqa: PLR0912
        self,
        expediente_id: str,
        despacho: str = "",
        logo_path: str = "",
        guardar_en: str = "",
        # edificabilidad optional params
        superficie_parcela: float = 0.0,
        coef_edificabilidad: float = 0.0,
        ocupacion_max_pct: float = 0.0,
        altura_max_m: float = 0.0,
        num_plantas: int = 0,
        # PEM optional params
        tipologia: str = "residencial_unifamiliar",
        calidad: str = "media",
        zona: str = "nacional",
        superficie_construida_m2: float = 0.0,
        # flags
        incluir_memoria: bool = True,
    ) -> dict[str, Any]:
        """Generate the full integrated project report PDF."""
        from adv_archon.core.memoria_descriptiva import generar_memoria_descriptiva
        from adv_archon.tools.edificabilidad import tool_calcular_edificabilidad
        from adv_archon.tools.pem import tool_calcular_pem

        if self._exp_store is None:
            return {"ok": False, "error": "No hay ExpedienteStore configurado."}

        exp = self._exp_store.get(expediente_id)
        if exp is None:
            return {"ok": False, "error": f"Expediente {expediente_id!r} no encontrado."}

        # Edificabilidad
        edif_result = None
        if superficie_parcela > 0 and coef_edificabilidad > 0:
            edif_result = tool_calcular_edificabilidad(
                superficie_parcela=superficie_parcela,
                coef_edificabilidad=coef_edificabilidad,
                ocupacion_max_pct=ocupacion_max_pct or 60.0,
                altura_max_m=altura_max_m or 9.0,
                num_plantas=num_plantas or 3,
            )
            if not edif_result.get("ok"):
                edif_result = None

        # PEM
        pem_result = None
        s_construida = superficie_construida_m2 or (
            superficie_parcela * coef_edificabilidad if superficie_parcela > 0 else 0
        )
        if s_construida > 0:
            pem_result = tool_calcular_pem(
                superficie_construida_m2=s_construida,
                tipologia=tipologia,
                calidad=calidad,
                zona=zona,
            )
            if not pem_result.get("ok"):
                pem_result = None

        # Energía (si hay coordenadas)
        energia_result = None
        if exp.latitude and exp.municipality:
            from adv_archon.tools.energia import tool_analisis_energetico
            energia_result = tool_analisis_energetico(
                municipio=exp.municipality,
                provincia=exp.province or "",
            )
            if not energia_result.get("ok"):
                energia_result = None

        # Memoria
        memoria_text = ""
        if incluir_memoria:
            try:
                memoria_text = generar_memoria_descriptiva(
                    exp, self._llm, knowledge_store=self._ks
                )
            except Exception:
                memoria_text = ""

        # Output path
        safe = exp.title[:40].replace(" ", "_")
        default_out = Path.home() / "Desktop" / f"Informe_{safe}.pdf"
        out = Path(guardar_en).expanduser() if guardar_en else default_out
        logo = Path(logo_path).expanduser() if logo_path else None

        try:
            generate_informe_proyecto(
                expediente=exp,
                output_path=out,
                despacho=despacho,
                logo_path=logo,
                edificabilidad_result=edif_result,
                pem_result=pem_result,
                memoria_text=memoria_text,
                energia_result=energia_result,
            )
        except Exception as exc:
            return {"ok": False, "error": f"Error generando PDF: {exc}"}

        secciones = ["portada", "datos del proyecto"]
        if edif_result:
            secciones.append("edificabilidad")
        if pem_result:
            secciones.append("PEM")
        if energia_result:
            secciones.append("pre-análisis energético")
        if memoria_text:
            secciones.append("memoria descriptiva")

        return {
            "ok": True,
            "expediente": exp.title,
            "pdf": str(out),
            "secciones": secciones,
        }
