from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class StudioCaseTemplate:
    code: str
    label: str
    decision_focus: str
    checklist: tuple[str, ...]
    base_hours_saved: int
    documents_generated: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CityNormativePack:
    municipality: str
    status: str
    label: str
    sources: tuple[str, ...]
    note: str


CASE_TEMPLATES: tuple[StudioCaseTemplate, ...] = (
    StudioCaseTemplate(
        code="cambio_uso_vivienda",
        label="Cambio de uso local a vivienda",
        decision_focus="Compatibilidad de uso, habitabilidad y condiciones sectoriales.",
        checklist=(
            "Compatibilidad urbanística del cambio de uso.",
            "Ordenanza, zona y grado de protección aplicable.",
            "Condiciones mínimas de vivienda, ventilación e iluminación.",
            "Afecciones sectoriales relevantes antes de invertir proyecto.",
            "Próximos pasos para consulta previa o licencia.",
        ),
        base_hours_saved=9,
        documents_generated=(
            "Informe preliminar de viabilidad",
            "Checklist de cambio de uso",
            "Resumen de fuentes oficiales",
        ),
    ),
    StudioCaseTemplate(
        code="vivienda_unifamiliar",
        label="Vivienda unifamiliar",
        decision_focus="Edificabilidad, ocupación, retranqueos y riesgos de parcela.",
        checklist=(
            "Clasificación y calificación urbanística.",
            "Edificabilidad, ocupación y altura máxima.",
            "Retranqueos, alineaciones y parcela mínima.",
            "Riesgos de inundabilidad, carreteras, costas o protección ambiental.",
            "Documentación mínima para anteproyecto.",
        ),
        base_hours_saved=11,
        documents_generated=(
            "Informe preliminar de parcela",
            "Matriz de riesgos urbanísticos",
            "Anexo de fuentes sectoriales",
        ),
    ),
    StudioCaseTemplate(
        code="local_comercial",
        label="Local comercial",
        decision_focus="Uso admisible, actividad, accesibilidad e incidencias sectoriales.",
        checklist=(
            "Uso comercial permitido o condicionado.",
            "Compatibilidad con planta, fachada y entorno.",
            "Accesibilidad, evacuación y posibles limitaciones CTE.",
            "Afecciones urbanísticas o sectoriales previas.",
            "Próximos pasos para actividad o licencia.",
        ),
        base_hours_saved=7,
        documents_generated=(
            "Brief de viabilidad de local",
            "Checklist de actividad",
            "Resumen ejecutivo para cliente",
        ),
    ),
    StudioCaseTemplate(
        code="reforma",
        label="Reforma",
        decision_focus="Alcance de obra, compatibilidad normativa y documentación necesaria.",
        checklist=(
            "Tipo de intervención y alcance administrativo.",
            "Compatibilidad urbanística con edificio y uso existente.",
            "Protección patrimonial o ambiental si procede.",
            "Necesidad de proyecto, declaración responsable o licencia.",
            "Riesgos pendientes antes de presupuesto.",
        ),
        base_hours_saved=6,
        documents_generated=(
            "Informe de alcance preliminar",
            "Checklist de licencia o declaración",
            "Listado de información pendiente",
        ),
    ),
    StudioCaseTemplate(
        code="obra_nueva",
        label="Obra nueva",
        decision_focus="Viabilidad urbanística de parcela y condicionantes críticos.",
        checklist=(
            "Clasificación del suelo y ordenanza aplicable.",
            "Parámetros de volumen, altura, ocupación y edificabilidad.",
            "Afecciones sectoriales críticas.",
            "Riesgo de incompatibilidad urbanística o falta de datos.",
            "Próximos pasos para anteproyecto y consulta municipal.",
        ),
        base_hours_saved=13,
        documents_generated=(
            "Informe de viabilidad de obra nueva",
            "Panel de riesgos de parcela",
            "Anexo técnico de fuentes consultadas",
        ),
    ),
)


CITY_PACKS: tuple[CityNormativePack, ...] = (
    CityNormativePack(
        municipality="Madrid",
        status="validado",
        label="Madrid Studio Pack",
        sources=("PGOU Madrid", "Catastro OVC", "SNCZI/CNIG", "IDE/IGN"),
        note="Paquete base validado para demos comerciales y expedientes preliminares.",
    ),
    CityNormativePack(
        municipality="Zaragoza",
        status="preliminar",
        label="Zaragoza Studio Pack",
        sources=("PGOU Zaragoza", "Catastro OVC", "SNCZI/CNIG"),
        note="Paquete operativo pendiente de revisión fina de ordenanzas.",
    ),
    CityNormativePack(
        municipality="Barcelona",
        status="preliminar",
        label="Barcelona Studio Pack",
        sources=("Planeamiento municipal", "Catastro OVC", "fuentes sectoriales"),
        note="Paquete previsto para validación por despacho colaborador.",
    ),
    CityNormativePack(
        municipality="Valencia",
        status="pendiente",
        label="Valencia Studio Pack",
        sources=("Planeamiento municipal", "Catastro OVC"),
        note="Pendiente de curación normativa antes de venta como paquete validado.",
    ),
    CityNormativePack(
        municipality="Sevilla",
        status="pendiente",
        label="Sevilla Studio Pack",
        sources=("Planeamiento municipal", "Catastro OVC"),
        note="Pendiente de curación normativa antes de venta como paquete validado.",
    ),
)


def case_template_options() -> list[tuple[str, str]]:
    return [(item.code, item.label) for item in CASE_TEMPLATES]


def get_case_template(code: str | None) -> StudioCaseTemplate:
    normalized = (code or "").strip()
    for template in CASE_TEMPLATES:
        if template.code == normalized:
            return template
    return CASE_TEMPLATES[0]


def city_pack_for(municipality: str | None) -> CityNormativePack | None:
    normalized = (municipality or "").strip().casefold()
    if not normalized:
        return None
    for pack in CITY_PACKS:
        if pack.municipality.casefold() == normalized:
            return pack
    return None


def build_studio_payload(
    *,
    case_type: str | None,
    municipality: str | None,
    site_context: dict[str, Any],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    template = get_case_template(case_type)
    pack = city_pack_for(municipality)
    checks = site_context.get("legal_checks") or []
    checks = checks if isinstance(checks, list) else []
    warning_count = sum(
        1
        for check in checks
        if isinstance(check, dict)
        and str(check.get("status") or "") in {"conditional", "pending_review", "missing"}
    )
    sources_count = _count_sources(site_context)
    verdict = str(analysis.get("verdict") or analysis.get("verdict_label") or "").casefold()
    decision = _decision_label(verdict, warning_count, bool(checks))
    hours_saved = template.base_hours_saved + min(warning_count, 4)
    return {
        "mode": "ADV ARCHON Studio Edition",
        "case_type": template.code,
        "case_label": template.label,
        "decision_focus": template.decision_focus,
        "decision": decision,
        "checklist": list(template.checklist),
        "estimated_value": {
            "hours_saved": hours_saved,
            "risks_detected": warning_count,
            "sources_consulted": sources_count,
            "documents_generated": len(template.documents_generated),
            "documents": list(template.documents_generated),
        },
        "city_pack": {
            "municipality": pack.municipality if pack else municipality or "",
            "status": pack.status if pack else "pendiente",
            "label": pack.label if pack else "Paquete municipal no configurado",
            "sources": list(pack.sources) if pack else [],
            "note": pack.note
            if pack
            else "Municipio pendiente de curación normativa para Studio Edition.",
        },
    }


def _decision_label(verdict: str, warning_count: int, has_checks: bool) -> str:
    if not has_checks:
        return "FALTA INFORMACIÓN"
    if verdict in {"no recomendable", "incumple", "nok"}:
        return "NO RECOMENDABLE"
    if warning_count >= 3:
        return "CONDICIONADO"
    if warning_count:
        return "CONDICIONADO"
    return "VIABLE"


def _count_sources(site_context: dict[str, Any]) -> int:
    keys = (
        "cadastral_ref",
        "parcel_detail",
        "flood_zone",
        "natura2000",
        "costas",
        "carreteras",
        "parcel_zoning",
    )
    return sum(1 for key in keys if site_context.get(key))


__all__ = [
    "CITY_PACKS",
    "CASE_TEMPLATES",
    "CityNormativePack",
    "StudioCaseTemplate",
    "build_studio_payload",
    "case_template_options",
    "city_pack_for",
    "get_case_template",
]
