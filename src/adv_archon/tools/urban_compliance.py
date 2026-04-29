from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from adv_archon.core.llm import LLMRouter
from adv_archon.core.llm_types import LLMMessage
from adv_archon.core.pgou_store import PGOUStore
from adv_archon.core.report_generator import generate_compliance_pdf
from adv_archon.tools.urban_plan import PlanData, plan_to_summary, read_plan


@dataclass(slots=True)
class ComplianceAnnotation:
    article_ref: str
    status: str          # "ok" | "warning" | "violation" | "info"
    description: str
    recommendation: str


@dataclass
class ComplianceReport:
    plan_path: str
    municipality: str
    generated_at: str
    annotations: list[ComplianceAnnotation]
    summary: str
    raw_analysis: str


@dataclass(slots=True)
class ToolResult:
    name: str
    payload: dict[str, Any]


class UrbanComplianceTools:
    def __init__(
        self,
        pgou_store: PGOUStore,
        llm: LLMRouter,
    ) -> None:
        self._store = pgou_store
        self._llm = llm

    # ------------------------------------------------------------------ #
    # Tool: pgou_add                                                       #
    # ------------------------------------------------------------------ #

    def pgou_add(self, municipality: str, text: str, source: str = "") -> ToolResult:
        """Index PGOU text for a municipality."""
        if not municipality.strip():
            return ToolResult(
                name="pgou_add",
                payload={"ok": False, "error": "El nombre del municipio no puede estar vacío."},
            )
        if not text.strip():
            return ToolResult(
                name="pgou_add",
                payload={"ok": False, "error": "El texto de la normativa está vacío."},
            )

        chunk_count = self._store.index_text(
            text,
            municipality=municipality,
            source=source,
        )
        return ToolResult(
            name="pgou_add",
            payload={
                "ok": True,
                "municipality": municipality,
                "chunks_indexed": chunk_count,
                "source": source,
            },
        )

    # ------------------------------------------------------------------ #
    # Tool: plan_compliance_check                                          #
    # ------------------------------------------------------------------ #

    def plan_compliance_check(self, plan_path: str, municipality: str) -> ToolResult:
        """Analyze an architectural plan against the PGOU of a municipality."""
        muni = self._store.get_municipality(municipality)
        if muni is None:
            indexed = [m.name for m in self._store.list_municipalities()]
            return ToolResult(
                name="plan_compliance_check",
                payload={
                    "ok": False,
                    "error": (
                        f"No hay normativa indexada para '{municipality}'. "
                        f"Municipios disponibles: {indexed or ['ninguno']}. "
                        "Usa pgou_add para indexar la normativa primero."
                    ),
                },
            )

        try:
            plan_data = read_plan(plan_path)
        except (FileNotFoundError, ValueError) as exc:
            return ToolResult(
                name="plan_compliance_check",
                payload={"ok": False, "error": str(exc)},
            )

        report = self._run_analysis(plan_data, municipality)

        return ToolResult(
            name="plan_compliance_check",
            payload={
                "ok": True,
                "plan": Path(plan_path).name,
                "municipality": municipality,
                "generated_at": report.generated_at,
                "summary": report.summary,
                "annotations": [
                    {
                        "article_ref": a.article_ref,
                        "status": a.status,
                        "description": a.description,
                        "recommendation": a.recommendation,
                    }
                    for a in report.annotations
                ],
                "full_analysis": report.raw_analysis,
            },
        )

    # ------------------------------------------------------------------ #
    # Tool: pgou_status                                                    #
    # ------------------------------------------------------------------ #

    def pgou_status(self) -> ToolResult:
        """List all indexed municipalities."""
        munis = self._store.list_municipalities()
        return ToolResult(
            name="pgou_status",
            payload={
                "municipalities": [
                    {
                        "name": m.name,
                        "chunks": m.chunk_count,
                        "source": m.source,
                        "indexed_at": m.indexed_at,
                    }
                    for m in munis
                ],
                "total": len(munis),
            },
        )

    # ------------------------------------------------------------------ #
    # Tool: plan_compliance_export                                         #
    # ------------------------------------------------------------------ #

    def plan_compliance_export(
        self,
        plan_path: str,
        municipality: str,
        output_path: str | None = None,
    ) -> ToolResult:
        """Run compliance check and export the result as a professional PDF report."""
        check = self.plan_compliance_check(plan_path, municipality)
        if not check.payload.get("ok"):
            return ToolResult(
                name="plan_compliance_export",
                payload=check.payload,
            )

        if not output_path:
            stem = Path(plan_path).stem
            safe_muni = municipality.lower().replace(" ", "_")
            ts = datetime.now().strftime("%Y%m%d_%H%M")
            output_path = str(
                Path.home() / "Desktop" / f"informe_{safe_muni}_{stem}_{ts}.pdf"
            )

        out = Path(output_path).expanduser()
        try:
            generate_compliance_pdf(
                plan_path=plan_path,
                municipality=municipality,
                generated_at=check.payload["generated_at"],
                summary=check.payload["summary"],
                annotations=check.payload["annotations"],
                full_analysis=check.payload["full_analysis"],
                output_path=out,
            )
        except Exception as exc:
            return ToolResult(
                name="plan_compliance_export",
                payload={"ok": False, "error": f"Error generando PDF: {exc}"},
            )

        return ToolResult(
            name="plan_compliance_export",
            payload={
                "ok": True,
                "pdf_path": str(out),
                "plan": Path(plan_path).name,
                "municipality": municipality,
                "summary": check.payload["summary"],
                "annotations_count": len(check.payload["annotations"]),
            },
        )

    # ------------------------------------------------------------------ #
    # Private: LLM analysis                                               #
    # ------------------------------------------------------------------ #

    def _run_analysis(self, plan: PlanData, municipality: str) -> ComplianceReport:
        search_query = _build_search_query(plan)
        search_result = self._store.search(
            search_query,
            municipality=municipality,
            limit=10,
        )

        normativa_block = _format_normativa(search_result.chunks)
        plan_summary = plan_to_summary(plan)

        system_prompt = (
            "Eres un arquitecto técnico experto en normativa urbanística española. "
            "Tu tarea es analizar un plano arquitectónico y verificar su conformidad "
            "con la normativa del PGOU del municipio indicado. "
            "Sé preciso, cita artículos concretos cuando los tengas, "
            "e indica claramente qué cumple, qué podría incumplir y qué necesita revisión. "
            "Responde en español."
        )

        user_message = (
            f"MUNICIPIO: {municipality}\n\n"
            f"=== DATOS EXTRAÍDOS DEL PLANO ===\n{plan_summary}\n\n"
            f"=== FRAGMENTOS RELEVANTES DEL PGOU DE {municipality.upper()} ===\n"
            f"{normativa_block}\n\n"
            "Por favor, proporciona:\n"
            "1. RESUMEN EJECUTIVO: 3-5 líneas con el veredicto general.\n"
            "2. ANOTACIONES DETALLADAS: Para cada aspecto relevante del plano "
            "(altura, superficies, retranqueos, usos, ocupación, edificabilidad), "
            "indica si CUMPLE ✓, POSIBLE INCUMPLIMIENTO ⚠, INCUMPLE ✗ o REQUIERE VERIFICACIÓN ?, "
            "citando el artículo o norma aplicable.\n"
            "3. RECOMENDACIONES: Qué debe revisar o corregir el arquitecto.\n"
        )

        response = self._llm.complete(
            [LLMMessage(role="user", content=user_message)],
            system_prompt=system_prompt,
            task="reasoning",
        )

        annotations = _parse_annotations(response.text)
        summary = _extract_summary(response.text)

        return ComplianceReport(
            plan_path=plan.path,
            municipality=municipality,
            generated_at=datetime.now(UTC).isoformat(),
            annotations=annotations,
            summary=summary,
            raw_analysis=response.text,
        )


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _build_search_query(plan: PlanData) -> str:
    parts: list[str] = ["normativa urbanística edificación"]
    if plan.building_use:
        parts.extend(plan.building_use[:3])
    if plan.heights_m:
        parts.append("altura máxima edificación")
    if plan.areas_m2:
        parts.append("superficie edificable parcela")
    if plan.setbacks_m:
        parts.append("retranqueos alineaciones")
    if plan.floors:
        parts.append("número plantas alturas")
    parts.extend(["ocupación edificabilidad", "usos permitidos"])
    return " ".join(parts)


def _format_normativa(chunks: list) -> str:
    if not chunks:
        return "No se encontraron fragmentos relevantes de normativa indexada."
    sections: list[str] = []
    for chunk in chunks:
        header = f"[{chunk.article_ref}]" if chunk.article_ref else "[Normativa]"
        if chunk.title and chunk.title != chunk.article_ref:
            header += f" {chunk.title[:80]}"
        sections.append(f"{header}\n{chunk.text[:600]}")
    return "\n\n---\n\n".join(sections)


_STATUS_MAP = {
    "✓": "ok",
    "cumple": "ok",
    "⚠": "warning",
    "posible incumplimiento": "warning",
    "requiere verificación": "info",
    "requiere verificacion": "info",
    "?": "info",
    "✗": "violation",
    "incumple": "violation",
}


def _parse_annotations(text: str) -> list[ComplianceAnnotation]:
    annotations: list[ComplianceAnnotation] = []
    lines = text.split("\n")
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        status = "info"
        for marker, s in _STATUS_MAP.items():
            if marker in line_stripped.lower():
                status = s
                break
        if any(m in line_stripped for m in ("✓", "⚠", "✗", "CUMPLE", "INCUMPLE", "POSIBLE", "REQUIERE")):
            annotations.append(
                ComplianceAnnotation(
                    article_ref="",
                    status=status,
                    description=line_stripped[:300],
                    recommendation="",
                )
            )
    return annotations[:30]


def _extract_summary(text: str) -> str:
    lower = text.lower()
    for marker in ("resumen ejecutivo", "resumen:", "1.", "veredicto"):
        idx = lower.find(marker)
        if idx >= 0:
            snippet = text[idx : idx + 600]
            lines = [l.strip() for l in snippet.split("\n") if l.strip()]
            return "\n".join(lines[:5])
    return text[:400]
