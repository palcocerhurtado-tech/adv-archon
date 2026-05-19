from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from adv_archon.core.studio import CityNormativePack, city_pack_for


@dataclass(frozen=True, slots=True)
class QualityIssue:
    code: str
    label: str
    severity: str


@dataclass(frozen=True, slots=True)
class SourceTrace:
    name: str
    status: str
    source: str
    official_data: str
    archon_inference: str
    pending_validation: str


@dataclass(frozen=True, slots=True)
class ArchitectReview:
    status: str
    label: str
    note: str
    include_in_report: bool


@dataclass(frozen=True, slots=True)
class ExpedienteQuality:
    completeness: str
    completeness_label: str
    risk_level: str
    risk_label: str
    missing_items: tuple[QualityIssue, ...]
    sources_consulted_ok: bool
    normative_pack: CityNormativePack | None
    source_traces: tuple[SourceTrace, ...]
    architect_review: ArchitectReview

    def as_payload(self) -> dict[str, Any]:
        return {
            "completeness": self.completeness,
            "completeness_label": self.completeness_label,
            "risk_level": self.risk_level,
            "risk_label": self.risk_label,
            "missing_items": [issue.__dict__ for issue in self.missing_items],
            "sources_consulted_ok": self.sources_consulted_ok,
            "normative_pack": self.normative_pack.__dict__
            if self.normative_pack
            else None,
            "source_traces": [trace.__dict__ for trace in self.source_traces],
            "architect_review": self.architect_review.__dict__,
        }


_REVIEW_LABELS = {
    "pending": "Pendiente de revisión",
    "confirmed": "Confirmado por arquitecto",
    "needs_correction": "Corregir antes de emitir",
    "excluded": "Excluir del informe",
}


def build_review_state(
    raw: str | dict[str, Any] | None,
    *,
    action: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    state = _loads_dict(raw)
    current_status = str(state.get("status") or "pending")
    current_note = str(state.get("note") or "")
    include = bool(state.get("include_in_report", True))
    action = (action or "").strip()
    if action == "confirmed":
        current_status = "confirmed"
        include = True
    elif action == "needs_correction":
        current_status = "needs_correction"
        include = True
    elif action == "excluded":
        current_status = "excluded"
        include = False
    elif action == "include":
        current_status = "pending"
        include = True
    if note is not None:
        current_note = note.strip()
    return {
        "status": current_status,
        "label": _REVIEW_LABELS.get(current_status, _REVIEW_LABELS["pending"]),
        "note": current_note,
        "include_in_report": include,
    }


def evaluate_expediente_quality(expediente: Any) -> ExpedienteQuality:
    site_context = _loads_dict(getattr(expediente, "site_context", ""))
    review = _review_from_raw(getattr(expediente, "review_state", ""))
    municipality = (
        str(getattr(expediente, "municipality", "") or "")
        or str(site_context.get("municipality") or "")
    )
    pack = city_pack_for(municipality)
    checks = site_context.get("legal_checks") if site_context else []
    checks = checks if isinstance(checks, list) else []

    missing: list[QualityIssue] = []
    if not str(getattr(expediente, "plan_path", "") or "").strip():
        missing.append(QualityIssue("plan", "Falta plano adjunto", "medium"))
    if not (
        str(getattr(expediente, "cadastral_ref", "") or "").strip()
        or str(site_context.get("cadastral_ref") or "").strip()
    ):
        missing.append(
            QualityIssue("cadastral_ref", "Falta referencia catastral", "high")
        )
    if not site_context:
        missing.append(QualityIssue("site_context", "Falta contexto de parcela", "high"))
    if not pack:
        missing.append(
            QualityIssue("municipal_pack", "Municipio sin paquete normativo", "medium")
        )
    elif pack.status != "validado":
        missing.append(
            QualityIssue(
                "pgou_validated",
                f"PGOU municipal en estado {pack.status}",
                "medium" if pack.status == "preliminar" else "high",
            )
        )
    if not checks:
        missing.append(QualityIssue("legal_checks", "Faltan checks legales", "high"))

    statuses = {
        str(check.get("status") or "")
        for check in checks
        if isinstance(check, dict)
    }
    if "missing" in statuses:
        missing.append(QualityIssue("legal_missing", "Hay checks sin dato", "high"))
    if "pending_review" in statuses:
        missing.append(
            QualityIssue("pending_review", "Hay fuentes pendientes de revisión", "medium")
        )

    required_sources = ("parcel_detail", "flood_zone", "natura2000", "costas", "carreteras")
    consulted = [key for key in required_sources if site_context.get(key)]
    sources_ok = bool(site_context.get("cadastral_ref")) and len(consulted) >= 4
    if not sources_ok:
        missing.append(
            QualityIssue(
                "official_sources",
                "No constan todas las fuentes oficiales básicas",
                "medium",
            )
        )

    high = any(issue.severity == "high" for issue in missing)
    medium = any(issue.severity == "medium" for issue in missing)
    conditional = "conditional" in statuses
    if high:
        risk_level = "alto"
        risk_label = "Riesgo jurídico alto"
    elif medium or conditional:
        risk_level = "medio"
        risk_label = "Riesgo jurídico medio"
    else:
        risk_level = "bajo"
        risk_label = "Riesgo jurídico bajo"

    completeness = "completo" if not missing and sources_ok else "incompleto"
    completeness_label = (
        "Expediente completo"
        if completeness == "completo"
        else "Expediente incompleto"
    )
    return ExpedienteQuality(
        completeness=completeness,
        completeness_label=completeness_label,
        risk_level=risk_level,
        risk_label=risk_label,
        missing_items=tuple(_dedupe_issues(missing)),
        sources_consulted_ok=sources_ok,
        normative_pack=pack,
        source_traces=tuple(_build_source_traces(site_context, pack)),
        architect_review=review,
    )


def _review_from_raw(raw: str | dict[str, Any] | None) -> ArchitectReview:
    state = build_review_state(raw)
    return ArchitectReview(
        status=str(state["status"]),
        label=str(state["label"]),
        note=str(state["note"]),
        include_in_report=bool(state["include_in_report"]),
    )


def _loads_dict(raw: str | dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _dedupe_issues(issues: list[QualityIssue]) -> list[QualityIssue]:
    seen: set[str] = set()
    result: list[QualityIssue] = []
    for issue in issues:
        if issue.code in seen:
            continue
        seen.add(issue.code)
        result.append(issue)
    return result


def _build_source_traces(
    site_context: dict[str, Any],
    pack: CityNormativePack | None,
) -> list[SourceTrace]:
    parcel = _loads_dict(site_context.get("parcel_detail"))
    zoning = _loads_dict(site_context.get("parcel_zoning"))
    flood = _loads_dict(site_context.get("flood_zone"))
    natura = _loads_dict(site_context.get("natura2000"))
    costas = _loads_dict(site_context.get("costas"))
    roads = _loads_dict(site_context.get("carreteras"))
    return [
        SourceTrace(
            name="Catastro",
            status="consultado" if site_context.get("cadastral_ref") or parcel else "pendiente",
            source=str(parcel.get("source") or "Catastro OVC"),
            official_data=_first(
                site_context.get("cadastral_ref"),
                parcel.get("surface_m2") and f"Superficie {parcel.get('surface_m2')} m2",
                parcel.get("use_detail"),
            ),
            archon_inference="Identificación parcelaria base para el expediente.",
            pending_validation=(
                "Contrastar titularidad y descripción completa si afecta al encargo."
            ),
        ),
        SourceTrace(
            name="PGOU municipal",
            status=pack.status if pack else "pendiente",
            source=_pack_source(pack),
            official_data=str(zoning.get("summary") or "PGOU textual y paquete municipal."),
            archon_inference="Zonificación preliminar; no sustituye plano/visor municipal.",
            pending_validation="Confirmar ordenanza exacta y vigencia en sede o visor municipal.",
        ),
        SourceTrace(
            name="SNCZI",
            status="consultado" if flood else "pendiente",
            source=str(flood.get("source") or "SNCZI/CNIG"),
            official_data=_yes_no(flood.get("in_flood_zone"), "Afección de inundabilidad"),
            archon_inference="Cribado sectorial hidráulico a partir de fuente oficial.",
            pending_validation="Revisar organismo de cuenca si el expediente es sensible.",
        ),
        SourceTrace(
            name="Red Natura 2000",
            status="consultado" if natura else "pendiente",
            source=str(natura.get("source") or "Red Natura 2000/CNIG"),
            official_data=_yes_no(natura.get("in_protected_area"), "Área protegida"),
            archon_inference="Cribado ambiental preliminar sobre geometría oficial.",
            pending_validation="Confirmar limitaciones ambientales con administración competente.",
        ),
        SourceTrace(
            name="Costas",
            status="consultado" if costas else "pendiente",
            source=str(costas.get("source") or "SIGCOSTAS/MITECO"),
            official_data=_yes_no(costas.get("in_public_domain"), "Dominio público litoral"),
            archon_inference="Cribado litoral preliminar.",
            pending_validation="Confirmar deslinde/servidumbres si hay proximidad al litoral.",
        ),
        SourceTrace(
            name="Carreteras",
            status="consultado" if roads else "pendiente",
            source=str(roads.get("source") or "Transportes INSPIRE/CNIG"),
            official_data=_yes_no(roads.get("in_affection_zone"), "Afección viaria"),
            archon_inference=(
                "Cribado geométrico sobre viario oficial; no delimita servidumbre jurídica."
            ),
            pending_validation="Confirmar línea legal con la administración titular de la vía.",
        ),
    ]


def _pack_source(pack: CityNormativePack | None) -> str:
    if not pack:
        return "Paquete municipal pendiente"
    source = pack.sources[0] if pack.sources else pack.label
    return f"{source} · actualización {pack.last_updated}"


def _first(*values: object) -> str:
    for value in values:
        if value:
            return str(value)
    return "Dato no disponible"


def _yes_no(value: object, label: str) -> str:
    if value is True:
        return f"{label}: sí"
    if value is False:
        return f"{label}: no"
    return f"{label}: sin dato"


def review_state_json(
    raw: str | dict[str, Any] | None,
    *,
    action: str | None = None,
    note: str | None = None,
) -> str:
    return json.dumps(
        build_review_state(raw, action=action, note=note),
        ensure_ascii=False,
    )


__all__ = [
    "ArchitectReview",
    "ExpedienteQuality",
    "QualityIssue",
    "SourceTrace",
    "build_review_state",
    "evaluate_expediente_quality",
    "review_state_json",
]
