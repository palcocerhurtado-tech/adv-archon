"""Preliminary expediente analysis (PySide6-free, headless-testable).

Pure business logic extracted from the desktop glue layer so it can be unit
tested without a Qt runtime.  Produces a preliminary, NON-BINDING screening of
an expediente's sectorial legal checks.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

# Maps a sectorial check status to an annotation severity used by the UI.
_STATUS_MAP = {
    "ready": "ok",
    "not_applicable": "info",
    "conditional": "warning",
    "pending_review": "info",
    "missing": "violation",
}


def build_expediente_analysis(exp: Any) -> dict[str, Any]:
    """Build a preliminary verdict + annotations for an expediente.

    The result is a screening aid only; it never constitutes a binding
    professional or legal opinion (see :mod:`adv_archon.core.legal`).
    """
    from adv_archon.core.studio import get_case_template

    template = get_case_template(getattr(exp, "case_type", ""))
    try:
        ctx = json.loads(exp.site_context) if exp.site_context else {}
    except (TypeError, ValueError):
        ctx = {}
    checks = ctx.get("legal_checks") if isinstance(ctx, dict) else []
    checks = checks if isinstance(checks, list) else []
    statuses = {
        str(check.get("status") or "")
        for check in checks
        if isinstance(check, dict)
    }
    if not checks:
        verdict = "revisar"
        verdict_label = "REVISAR"
        summary = (
            "Falta contexto legal completo. Debe resolverse parcela, PGOU y fuentes "
            "sectoriales antes de emitir criterio profesional."
        )
    elif {"pending_review", "missing"} & statuses:
        verdict = "revisar"
        verdict_label = "REVISAR"
        summary = (
            "Hay comprobaciones pendientes o datos insuficientes. Requiere revisión "
            "técnica antes de cerrar el informe."
        )
    elif "conditional" in statuses:
        verdict = "condicionado"
        verdict_label = "CONDICIONADO"
        summary = (
            "Se detectan condiciones o afecciones que deben contrastarse con el "
            "expediente y la administración competente."
        )
    else:
        verdict = "viable"
        verdict_label = "VIABLE"
        summary = (
            "No se detectan alertas sectoriales relevantes en el cribado preliminar. "
            "Confirmar siempre ordenanza y plano de proyecto."
        )

    annotations: list[dict[str, str]] = []
    next_steps: list[str] = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        status = str(check.get("status") or "")
        title = str(check.get("title") or "")
        detail = str(check.get("detail") or "")
        action = str(check.get("recommended_action") or "")
        annotations.append(
            {
                "status": _STATUS_MAP.get(status, "info"),
                "description": f"{title}: {detail}".strip(": "),
                "recommendation": action,
            }
        )
        if status not in {"ready", "not_applicable"} and action:
            next_steps.append(action)
    if getattr(exp, "plan_path", ""):
        next_steps.append("Revisar el plano adjunto frente a la ordenanza aplicable.")
    for item in template.checklist:
        if len(next_steps) >= 12:
            break
        next_steps.append(item)
    return {
        "verdict": verdict,
        "verdict_label": verdict_label,
        "summary": f"{template.label}. {summary}",
        "annotations": annotations[:30],
        "next_steps": next_steps[:12],
        "generated_at": datetime.now().isoformat(timespec="minutes"),
    }
