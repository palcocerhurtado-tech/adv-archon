from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ArchitectBrainProfile:
    name: str
    mission: str
    response_contract: tuple[str, ...]
    automatic_actions: tuple[str, ...]
    confirmation_actions: tuple[str, ...]
    blocked_actions: tuple[str, ...]


DEFAULT_ARCHITECT_BRAIN = ArchitectBrainProfile(
    name="ADV ARCHON Architect Brain v1",
    mission=(
        "Gestionar expedientes urbanisticos para despachos de arquitectura en Espana: "
        "detectar faltas, consultar fuentes oficiales, separar dato e inferencia y "
        "preparar un dictamen preliminar revisable."
    ),
    response_contract=(
        "Dictamen breve",
        "Datos oficiales usados",
        "Inferencia preliminar de ARCHON",
        "Riesgos o bloqueos",
        "Proximos pasos",
    ),
    automatic_actions=(
        "consultar fuentes oficiales disponibles",
        "detectar informacion ausente",
        "resumir riesgos y evidencias",
        "proponer el siguiente paso del expediente",
    ),
    confirmation_actions=(
        "exportar informe",
        "marcar PGOU u ordenanza como validada",
        "aceptar, excluir o reforzar advertencias",
        "continuar sin plano o con fuentes incompletas",
    ),
    blocked_actions=(
        "inventar normativa, articulos, parametros urbanisticos o capas juridicas",
        "presentar PGOU preliminar como validado",
        "ocultar afecciones sectoriales o incertidumbre juridica",
        "sustituir la revision tecnica responsable del arquitecto",
    ),
)


def build_architect_brain_section(*, compact: bool = False) -> str:
    """Return the stable local-first operating contract for urbanism answers."""
    profile = DEFAULT_ARCHITECT_BRAIN
    lines = [
        "## Architect Brain",
        f"- Identity: {profile.name}.",
        f"- Mission: {profile.mission}",
        "- Operating mode: actua como gestor de expediente, no como chatbot generico.",
        (
            "- Source discipline: separa siempre dato oficial, inferencia preliminar "
            "y pendiente de validacion."
        ),
        "- Legal honesty: si no consta en fuentes oficiales o PGOU indexado, di que no consta.",
        (
            "- Spanish practice: razona para arquitectura y urbanismo espanoles; "
            "menciona PGOU, Catastro, afecciones sectoriales y revision tecnica "
            "cuando proceda."
        ),
    ]
    if not compact:
        lines.extend(
            [
                "- Response contract: " + "; ".join(profile.response_contract) + ".",
                "- Automatic actions: " + "; ".join(profile.automatic_actions) + ".",
                "- Requires confirmation: " + "; ".join(profile.confirmation_actions) + ".",
                "- Blocked actions: " + "; ".join(profile.blocked_actions) + ".",
                (
                    "- When the expediente is incomplete, ask only the blocking question "
                    "and continue with a limited preliminary review if the user accepts."
                ),
                (
                    "- Voice mode: spoken answer must be short; written detail can "
                    "include evidence, risks and next steps."
                ),
            ]
        )
    else:
        lines.append("- Keep voice answers short and route detail to screen.")
    return "\n".join(lines)


def build_expediente_brain_brief(expediente: Any) -> str:
    """Build a compact active-expediente briefing for the agent prompt."""
    if expediente is None:
        return ""

    site_context = _loads_dict(getattr(expediente, "site_context", ""))
    analysis = _loads_dict(getattr(expediente, "analysis_result", ""))
    quality = _loads_dict(getattr(expediente, "quality_result", ""))
    reviews = _loads_dict(getattr(expediente, "agent_step_reviews", ""))
    history = _loads_list(getattr(expediente, "agent_history", ""))

    title = _clean(getattr(expediente, "title", "")) or "Expediente activo"
    municipality = _clean(getattr(expediente, "municipality", ""))
    province = _clean(getattr(expediente, "province", ""))
    address = _clean(getattr(expediente, "address", ""))
    cadastral_ref = _clean(getattr(expediente, "cadastral_ref", "")) or _clean(
        site_context.get("cadastral_ref", "")
    )
    case_type = _clean(getattr(expediente, "case_type", ""))
    status = _clean(getattr(expediente, "status", ""))
    plan_path = _clean(getattr(expediente, "plan_path", ""))
    report_path = _clean(getattr(expediente, "report_path", ""))
    quality_score = getattr(expediente, "quality_score", None)

    missing = _missing_inputs(expediente, site_context)
    sectorial = _sectorial_summary(site_context)
    legal_checks = _legal_checks_summary(site_context)
    verdict = _clean(analysis.get("verdict", "")) or _clean(analysis.get("decision", ""))
    summary = _clean(analysis.get("summary", ""))
    quality_verdict = _clean(quality.get("verdict", ""))
    review_summary = _review_summary(reviews)
    recent_event = _recent_event_summary(history)

    lines = [
        "## Active Expediente Briefing",
        f"- Title: {title}",
    ]
    if case_type:
        lines.append(f"- Case type: {case_type}")
    if status:
        lines.append(f"- Status: {status}")
    if address or municipality or province:
        location = ", ".join(item for item in (address, municipality, province) if item)
        lines.append(f"- Location: {location}")
    if cadastral_ref:
        lines.append(f"- Cadastral reference: {cadastral_ref}")
    coords = _coordinates(expediente)
    if coords:
        lines.append(f"- Coordinates: {coords}")
    lines.append(f"- Plan: {'attached' if plan_path else 'missing'}")
    lines.append(f"- Report: {'generated' if report_path else 'pending'}")
    if missing:
        lines.append("- Missing or weak inputs: " + "; ".join(missing[:6]))
    if sectorial:
        lines.append("- Sectorial sources: " + sectorial)
    if legal_checks:
        lines.append("- Legal checks: " + legal_checks)
    if verdict:
        lines.append(f"- Current verdict: {verdict}")
    if summary:
        lines.append(f"- Current analysis summary: {_truncate(summary, 420)}")
    if quality_score is not None or quality_verdict:
        score_text = f"{quality_score}/100" if quality_score is not None else "sin score"
        verdict_suffix = f" ({quality_verdict})" if quality_verdict else ""
        lines.append(f"- Local quality judge: {score_text}{verdict_suffix}")
    if review_summary:
        lines.append("- Architect review: " + review_summary)
    if recent_event:
        lines.append("- Last agent event: " + recent_event)
    lines.append(
        "- Use this briefing as context only; do not treat missing or preliminary "
        "fields as official validation."
    )
    return "\n".join(lines)


def _loads_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        data = json.loads(str(raw))
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _loads_list(raw: Any) -> list[Any]:
    if isinstance(raw, list):
        return raw
    if not raw:
        return []
    try:
        data = json.loads(str(raw))
    except (TypeError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _missing_inputs(expediente: Any, site_context: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not _clean(getattr(expediente, "address", "")):
        missing.append("address")
    if not _clean(getattr(expediente, "cadastral_ref", "")) and not _clean(
        site_context.get("cadastral_ref", "")
    ):
        missing.append("cadastral reference")
    if not _clean(getattr(expediente, "plan_path", "")):
        missing.append("plan/document")
    if not site_context:
        missing.append("site context")
    if not _clean(getattr(expediente, "analysis_result", "")):
        missing.append("preliminary analysis")
    return missing


def _sectorial_summary(site_context: dict[str, Any]) -> str:
    if not site_context:
        return ""
    entries: list[str] = []
    mapping = (
        ("flood_zone", "SNCZI"),
        ("natura2000", "Red Natura 2000"),
        ("costas", "Costas"),
        ("carreteras", "Carreteras"),
    )
    for key, label in mapping:
        value = site_context.get(key)
        if isinstance(value, dict):
            status = _source_status(value)
            entries.append(f"{label}={status}")
        elif value is None:
            entries.append(f"{label}=missing")
    return "; ".join(entries)


def _source_status(value: dict[str, Any]) -> str:
    if value.get("error"):
        return "error"
    flags = (
        "in_flood_zone",
        "in_protected_area",
        "in_public_domain",
        "in_protection_servitude",
        "in_affection_zone",
        "in_domain_zone",
        "in_servitude_zone",
    )
    if any(bool(value.get(flag)) for flag in flags):
        return "affected"
    if value:
        return "clear"
    return "missing"


def _legal_checks_summary(site_context: dict[str, Any]) -> str:
    checks = site_context.get("legal_checks")
    if not isinstance(checks, list):
        return ""
    chunks: list[str] = []
    for check in checks[:8]:
        if not isinstance(check, dict):
            continue
        title = _clean(check.get("title") or check.get("id") or "check")
        status = _clean(check.get("status", "unknown"))
        chunks.append(f"{title}={status}")
    return "; ".join(chunks)


def _review_summary(reviews: dict[str, Any]) -> str:
    if not reviews:
        return ""
    counts: dict[str, int] = {}
    for item in reviews.values():
        if not isinstance(item, dict):
            continue
        status = _clean(item.get("status", "")) or "unknown"
        counts[status] = counts.get(status, 0) + 1
    if not counts:
        return ""
    return "; ".join(f"{status}={count}" for status, count in sorted(counts.items()))


def _recent_event_summary(history: list[Any]) -> str:
    if not history:
        return ""
    last = history[-1]
    if not isinstance(last, dict):
        return ""
    title = _clean(last.get("title", ""))
    status = _clean(last.get("status", ""))
    message = _clean(last.get("message", ""))
    summary = " · ".join(item for item in (title, status, message) if item)
    return _truncate(summary, 260)


def _coordinates(expediente: Any) -> str:
    lat = getattr(expediente, "latitude", None)
    lon = getattr(expediente, "longitude", None)
    if lat is None or lon is None:
        return ""
    try:
        return f"{float(lat):.6f}, {float(lon):.6f}"
    except (TypeError, ValueError):
        return ""


def _truncate(text: str, max_chars: int) -> str:
    text = _clean(text)
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 16)].rstrip() + " [...truncated]"
