from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from adv_archon.core.llm import LLMRouter
from adv_archon.core.llm_types import LLMMessage
from adv_archon.core.pgou_store import PGOUChunk, PGOUStore
from adv_archon.core.report_generator import generate_compliance_pdf
from adv_archon.tools.pgou_scraper import PGOUScraper
from adv_archon.tools.urban_plan import PlanData, plan_to_summary, read_plan

if TYPE_CHECKING:
    from adv_archon.tools.geo_tools import GeoTools


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
        *,
        geo_tools: GeoTools | None = None,
    ) -> None:
        self._store = pgou_store
        self._llm = llm
        self._geo_tools = geo_tools
        self._scraper = PGOUScraper(pgou_store)

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
    # Tool: pgou_fetch                                                     #
    # ------------------------------------------------------------------ #

    def pgou_fetch(
        self,
        municipality: str,
        *,
        progress_cb: Any = None,
    ) -> ToolResult:
        """Auto-fetch and index PGOU from the official source for a catalogued municipality."""
        if not municipality.strip():
            return ToolResult(
                name="pgou_fetch",
                payload={"ok": False, "error": "El nombre del municipio no puede estar vacío."},
            )
        result = self._scraper.scrape_and_index(municipality, progress_cb=progress_cb)
        return ToolResult(name="pgou_fetch", payload=result)

    # ------------------------------------------------------------------ #
    # Tool: pgou_fetch_all                                                 #
    # ------------------------------------------------------------------ #

    def pgou_fetch_all(
        self,
        *,
        skip_indexed: bool = True,
        progress_cb: Any = None,
    ) -> ToolResult:
        """Fetch and index PGOU for all municipalities in the catalogue."""
        results = self._scraper.scrape_all(
            skip_indexed=skip_indexed,
            progress_cb=progress_cb,
        )
        ok_count = sum(1 for r in results if r.get("ok") and not r.get("skipped"))
        skipped = sum(1 for r in results if r.get("skipped"))
        failed = [r for r in results if not r.get("ok")]
        return ToolResult(
            name="pgou_fetch_all",
            payload={
                "ok": True,
                "indexed": ok_count,
                "skipped": skipped,
                "failed": len(failed),
                "failures": [
                    {"municipality": r.get("municipality"), "error": r.get("error")}
                    for r in failed
                ],
            },
        )

    # ------------------------------------------------------------------ #
    # Tool: pgou_catalogue                                                 #
    # ------------------------------------------------------------------ #

    def pgou_catalogue(self) -> ToolResult:
        """List all municipalities available for auto-fetch."""
        from adv_archon.tools.pgou_scraper import SOURCES
        indexed_names = {m.name for m in self._store.list_municipalities()}
        entries = [
            {
                "name": s.name,
                "indexed": s.name in indexed_names,
                "kind": s.kind,
            }
            for s in SOURCES
        ]
        return ToolResult(
            name="pgou_catalogue",
            payload={
                "total": len(entries),
                "indexed": sum(1 for e in entries if e["indexed"]),
                "municipalities": entries,
            },
        )

    # ------------------------------------------------------------------ #
    # Tool: plan_compliance_check                                          #
    # ------------------------------------------------------------------ #

    def plan_compliance_check(
        self,
        plan_path: str,
        municipality: str,
        *,
        site_context: dict[str, Any] | None = None,
    ) -> ToolResult:
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

        report = self._run_analysis(plan_data, municipality, site_context=site_context)

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

    def plan_compliance_check_by_coordinates(
        self,
        plan_path: str,
        latitude: float,
        longitude: float,
        *,
        auto_fetch: bool = True,
    ) -> ToolResult:
        """Resolve coordinates, ensure PGOU availability, then analyze the plan."""
        if self._geo_tools is None:
            return ToolResult(
                name="plan_compliance_check_by_coordinates",
                payload={
                    "ok": False,
                    "error": "La geolocalización no está configurada en este entorno.",
                },
            )

        site_result = self._geo_tools.site_compliance_context(latitude, longitude)
        site_payload = dict(site_result.payload)
        if not site_payload.get("ok"):
            return ToolResult(
                name="plan_compliance_check_by_coordinates",
                payload=site_payload,
            )

        municipality = str(site_payload.get("municipality") or "").strip()
        if not municipality:
            return ToolResult(
                name="plan_compliance_check_by_coordinates",
                payload={
                    **site_payload,
                    "ok": False,
                    "error": "No se ha podido determinar el municipio de esas coordenadas.",
                },
            )

        auto_fetched = False
        if not bool(site_payload.get("pgou_indexed")):
            if not auto_fetch:
                return ToolResult(
                    name="plan_compliance_check_by_coordinates",
                    payload={
                        **site_payload,
                        "ok": False,
                        "municipality": municipality,
                        "site_context": _site_context_summary(site_payload),
                        "error": (
                            f"La normativa de {municipality} no está indexada todavía. "
                            "Activa auto_fetch o ejecuta pgou_fetch primero."
                        ),
                    },
                )

            fetch_result = self.pgou_fetch(municipality)
            fetch_payload = dict(fetch_result.payload)
            if not fetch_payload.get("ok"):
                return ToolResult(
                    name="plan_compliance_check_by_coordinates",
                    payload={
                        **site_payload,
                        "ok": False,
                        "municipality": municipality,
                        "site_context": _site_context_summary(site_payload),
                        "error": (
                            f"No he podido descargar la normativa de {municipality} "
                            "antes del análisis. Detalle: "
                            f"{fetch_payload.get('error', 'sin detalle')}"
                        ),
                    },
                )
            auto_fetched = True
            site_payload["pgou_indexed"] = True
            site_payload["next_step"] = (
                f"La normativa PGOU de {municipality} se ha descargado e indexado "
                "automáticamente para este análisis."
            )

        check_result = self.plan_compliance_check(
            plan_path, municipality, site_context=_site_context_summary(site_payload)
        )
        check_payload = dict(check_result.payload)
        return ToolResult(
            name="plan_compliance_check_by_coordinates",
            payload={
                **check_payload,
                "municipality": municipality,
                "site_context": _site_context_summary(site_payload),
                "pgou_auto_fetched": auto_fetched,
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

    def _run_analysis(
        self,
        plan: PlanData,
        municipality: str,
        *,
        site_context: dict[str, Any] | None = None,
    ) -> ComplianceReport:
        search_query = _build_search_query(plan)
        search_result = self._store.search(
            search_query,
            municipality=municipality,
            limit=10,
        )

        normativa_block = _format_normativa(search_result.chunks)
        plan_summary = plan_to_summary(plan)
        site_block = _format_site_context(site_context) if site_context else ""

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
            + (f"=== DATOS OFICIALES DE PARCELA Y ZONA ===\n{site_block}\n\n" if site_block else "")
            + f"=== DATOS EXTRAÍDOS DEL PLANO ===\n{plan_summary}\n\n"
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

def _format_site_context(ctx: dict[str, Any]) -> str:
    """Render real parcel + flood data as a compact block for the LLM prompt."""
    lines: list[str] = []

    cadastral_ref = ctx.get("cadastral_ref", "")
    if cadastral_ref:
        lines.append(f"Referencia catastral: {cadastral_ref}")

    pd = ctx.get("parcel_detail") or {}
    if isinstance(pd, dict) and not pd.get("error"):
        if pd.get("surface_m2"):
            lines.append(f"Superficie construida real (Catastro): {pd['surface_m2']} m²")
        if pd.get("construction_year"):
            lines.append(f"Año de construcción (Catastro): {pd['construction_year']}")
        if pd.get("floors_above") is not None:
            lines.append(f"Plantas sobre rasante (Catastro): {pd['floors_above']}")
        if pd.get("floors_below"):
            lines.append(f"Plantas bajo rasante (Catastro): {pd['floors_below']}")
        if pd.get("use_detail"):
            lines.append(f"Uso catastral: {pd['use_detail']}")

    fz = ctx.get("flood_zone") or {}
    if isinstance(fz, dict) and fz.get("queried"):
        in_flood = fz.get("in_flood_zone")
        if in_flood is True:
            periods = ", ".join(fz.get("periods") or [])
            lines.append(
                f"⚠️ ZONA INUNDABLE (SNCZI/MITECO): SÍ — períodos {periods or 'detectado'}. "
                "Pueden aplicar restricciones sectoriales."
            )
        elif in_flood is False:
            lines.append("Zona inundable (SNCZI/MITECO): NO detectada (T10, T100, T500).")
        else:
            lines.append("Zona inundable (SNCZI): no disponible — verificar manualmente.")

    address = ctx.get("cadastral_address", "")
    if address:
        lines.append(f"Dirección catastral: {address}")

    return "\n".join(lines) if lines else ""


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


def _format_normativa(chunks: list[PGOUChunk]) -> str:
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
    markers = ("✓", "⚠", "✗", "CUMPLE", "INCUMPLE", "POSIBLE", "REQUIERE")
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
        if any(marker in line_stripped for marker in markers):
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
            lines = [line.strip() for line in snippet.split("\n") if line.strip()]
            return "\n".join(lines[:5])
    return text[:400]


def _site_context_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "latitude": payload.get("latitude"),
        "longitude": payload.get("longitude"),
        "municipality": payload.get("municipality", ""),
        "province": payload.get("province", ""),
        "autonomous_community": payload.get("autonomous_community", ""),
        "display_location": payload.get("display_location", ""),
        "cadastral_ref": payload.get("cadastral_ref", ""),
        "cadastral_address": payload.get("cadastral_address", ""),
        "cadastral_use": payload.get("cadastral_use", ""),
        "resolution": payload.get("resolution", ""),
        "confidence": payload.get("confidence", ""),
        "pgou_indexed": payload.get("pgou_indexed"),
        "next_step": payload.get("next_step"),
        "legal_readiness": payload.get("legal_readiness", ""),
        "legal_summary": payload.get("legal_summary", ""),
        "legal_checks": payload.get("legal_checks", []),
        "parcel_detail": payload.get("parcel_detail", {}),
        "flood_zone": payload.get("flood_zone", {}),
    }
