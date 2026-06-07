from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from adv_archon.core.expediente_quality import evaluate_expediente_quality
from adv_archon.core.office_memory import MunicipalityPolicy

AGENT_STEP_STATUS_LABELS = {
    "pending": "Pendiente",
    "in_progress": "En curso",
    "completed": "Completado",
    "needs_review": "Necesita revisión",
    "blocked": "Bloqueado",
}

AGENT_STEP_REVIEW_LABELS = {
    "pending": "Pendiente de arquitecto",
    "validated": "Validado por arquitecto",
    "accepted_warning": "Advertencia aceptada",
    "included": "Incluido en informe",
    "excluded": "Excluido del informe",
    "requested_repeat": "Repetición solicitada",
}


@dataclass(frozen=True, slots=True)
class AgentPlanStep:
    code: str
    title: str
    intent: str
    status: str
    official_data: str
    archon_inference: str
    confidence: str
    recommended_action: str
    review_status: str = "pending"
    review_label: str = "Pendiente de arquitecto"
    review_note: str = ""
    include_in_report: bool = True

    @property
    def status_label(self) -> str:
        return AGENT_STEP_STATUS_LABELS.get(self.status, self.status)

    def as_payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "title": self.title,
            "intent": self.intent,
            "status": self.status,
            "status_label": self.status_label,
            "official_data": self.official_data,
            "archon_inference": self.archon_inference,
            "confidence": self.confidence,
            "recommended_action": self.recommended_action,
            "review_status": self.review_status,
            "review_label": self.review_label,
            "review_note": self.review_note,
            "include_in_report": self.include_in_report,
        }


@dataclass(frozen=True, slots=True)
class AgentQuestion:
    code: str
    question: str
    reason: str

    def as_payload(self) -> dict[str, str]:
        return {
            "code": self.code,
            "question": self.question,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class AgentSourceLog:
    name: str
    status: str
    source: str
    official_data: str
    archon_inference: str
    pending_validation: str

    def as_payload(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status,
            "source": self.source,
            "official_data": self.official_data,
            "archon_inference": self.archon_inference,
            "pending_validation": self.pending_validation,
        }


@dataclass(frozen=True, slots=True)
class AgentRunEvent:
    step_code: str
    title: str
    status: str
    message: str
    created_at: str
    run_id: str = ""

    @property
    def status_label(self) -> str:
        return AGENT_STEP_STATUS_LABELS.get(self.status, self.status)

    def as_payload(self) -> dict[str, str]:
        return {
            "step_code": self.step_code,
            "title": self.title,
            "status": self.status,
            "status_label": self.status_label,
            "message": self.message,
            "created_at": self.created_at,
            "run_id": self.run_id,
        }


@dataclass(frozen=True, slots=True)
class AgentStepReview:
    step_code: str
    status: str
    label: str
    include_in_report: bool
    note: str
    updated_at: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "step_code": self.step_code,
            "status": self.status,
            "label": self.label,
            "include_in_report": self.include_in_report,
            "note": self.note,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True, slots=True)
class AgentPlan:
    verdict: str
    verdict_label: str
    confidence: str
    summary: str
    steps: tuple[AgentPlanStep, ...]
    questions: tuple[AgentQuestion, ...]
    source_log: tuple[AgentSourceLog, ...]

    def as_payload(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "verdict_label": self.verdict_label,
            "confidence": self.confidence,
            "summary": self.summary,
            "steps": [step.as_payload() for step in self.steps],
            "questions": [question.as_payload() for question in self.questions],
            "source_log": [item.as_payload() for item in self.source_log],
        }


def append_agent_event(
    raw_history: str | list[dict[str, Any]] | tuple[AgentRunEvent, ...] | None,
    *,
    step_code: str,
    title: str,
    status: str,
    message: str,
    run_id: str = "",
    created_at: str | None = None,
    max_events: int = 120,
) -> str:
    """Append one persistent event to an expediente agent history JSON field."""
    event = AgentRunEvent(
        step_code=step_code,
        title=title,
        status=status,
        message=message,
        created_at=created_at or datetime.now(UTC).isoformat(timespec="seconds"),
        run_id=run_id,
    )
    events = [item.as_payload() for item in load_agent_history(raw_history)]
    events.append(event.as_payload())
    if max_events > 0:
        events = events[-max_events:]
    return json.dumps(events, ensure_ascii=False)


def load_agent_history(
    raw_history: str | list[dict[str, Any]] | tuple[AgentRunEvent, ...] | None,
) -> tuple[AgentRunEvent, ...]:
    """Load agent history defensively from persisted JSON."""
    if isinstance(raw_history, tuple) and all(
        isinstance(item, AgentRunEvent) for item in raw_history
    ):
        return raw_history
    raw_items: list[Any]
    if isinstance(raw_history, list):
        raw_items = list(raw_history)
    elif isinstance(raw_history, str) and raw_history.strip():
        try:
            parsed = json.loads(raw_history)
        except (TypeError, ValueError):
            return ()
        raw_items = parsed if isinstance(parsed, list) else []
    else:
        raw_items = []
    events: list[AgentRunEvent] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        step_code = str(item.get("step_code") or item.get("code") or "").strip()
        title = str(item.get("title") or step_code or "Evento del agente").strip()
        status = str(item.get("status") or "pending").strip()
        message = str(item.get("message") or "").strip()
        created_at = str(item.get("created_at") or "").strip()
        run_id = str(item.get("run_id") or "").strip()
        if not step_code or not created_at:
            continue
        events.append(
            AgentRunEvent(
                step_code=step_code,
                title=title,
                status=status,
                message=message,
                created_at=created_at,
                run_id=run_id,
            )
        )
    return tuple(events)


def load_agent_step_reviews(
    raw_reviews: str | dict[str, Any] | None,
) -> dict[str, AgentStepReview]:
    """Load architect decisions by agent step from JSON."""
    if isinstance(raw_reviews, dict):
        raw_items = raw_reviews
    elif isinstance(raw_reviews, str) and raw_reviews.strip():
        try:
            parsed = json.loads(raw_reviews)
        except (TypeError, ValueError):
            return {}
        raw_items = parsed if isinstance(parsed, dict) else {}
    else:
        raw_items = {}
    reviews: dict[str, AgentStepReview] = {}
    for step_code, raw in raw_items.items():
        if not isinstance(raw, dict):
            continue
        code = str(raw.get("step_code") or step_code).strip()
        if not code:
            continue
        status = str(raw.get("status") or "pending").strip()
        label = str(raw.get("label") or AGENT_STEP_REVIEW_LABELS.get(status, status))
        note = str(raw.get("note") or "").strip()
        updated_at = str(raw.get("updated_at") or "").strip()
        include_in_report = bool(raw.get("include_in_report", True))
        reviews[code] = AgentStepReview(
            step_code=code,
            status=status,
            label=label,
            include_in_report=include_in_report,
            note=note,
            updated_at=updated_at,
        )
    return reviews


def update_agent_step_review(
    raw_reviews: str | dict[str, Any] | None,
    *,
    step_code: str,
    action: str,
    note: str = "",
    updated_at: str | None = None,
) -> str:
    """Persist one architect action over an agent step."""
    reviews = load_agent_step_reviews(raw_reviews)
    status = _review_status_from_action(action)
    include_in_report = _review_include_from_action(action, reviews.get(step_code))
    review = AgentStepReview(
        step_code=step_code,
        status=status,
        label=AGENT_STEP_REVIEW_LABELS.get(status, status),
        include_in_report=include_in_report,
        note=note.strip(),
        updated_at=updated_at or datetime.now(UTC).isoformat(timespec="seconds"),
    )
    payload = {code: item.as_payload() for code, item in reviews.items()}
    payload[step_code] = review.as_payload()
    return json.dumps(payload, ensure_ascii=False)


def build_expediente_agent_plan(
    expediente: Any,
    *,
    include_history: bool = True,
    office_policy: MunicipalityPolicy | None = None,
) -> AgentPlan:
    """Build the guided urban-planning agent plan for one expediente.

    The plan is deliberately derived from the expediente state instead of being
    another persisted workflow. That keeps the first Agent Mode robust: every
    refresh reflects the real dossier, official sources, analysis and architect
    review already stored in ADV ARCHON.
    """
    site_context = _loads_dict(getattr(expediente, "site_context", ""))
    analysis = _loads_dict(getattr(expediente, "analysis_result", ""))
    quality = evaluate_expediente_quality(expediente)

    address = str(getattr(expediente, "address", "") or "").strip()
    municipality = (
        str(getattr(expediente, "municipality", "") or "").strip()
        or str(site_context.get("municipality") or "").strip()
    )
    cadastral_ref = (
        str(getattr(expediente, "cadastral_ref", "") or "").strip()
        or str(site_context.get("cadastral_ref") or "").strip()
    )
    has_coords = bool(
        getattr(expediente, "latitude", None) and getattr(expediente, "longitude", None)
    )
    status = str(getattr(expediente, "status", "") or "")
    has_plan = bool(str(getattr(expediente, "plan_path", "") or "").strip())
    has_analysis = bool(analysis)
    review = quality.architect_review
    pack = quality.normative_pack
    legal_checks = site_context.get("legal_checks") if site_context else []
    legal_checks = legal_checks if isinstance(legal_checks, list) else []

    steps: tuple[AgentPlanStep, ...] = (
        _location_step(address, municipality, has_coords, status),
        _catastro_step(cadastral_ref, site_context),
        _sectorial_step(site_context),
        _pgou_step(municipality, site_context, pack, office_policy),
        _plan_document_step(has_plan),
        _dictamen_step(has_analysis, has_plan, site_context, analysis),
        _architect_review_step(review.status, review.label),
    )
    if include_history:
        steps = _apply_history_overlay(
            steps,
            load_agent_history(getattr(expediente, "agent_history", "")),
        )
    steps = _apply_step_reviews(
        steps,
        load_agent_step_reviews(getattr(expediente, "agent_step_reviews", "")),
    )
    questions = tuple(
        _build_questions(
            has_plan=has_plan,
            pack_status=pack.status if pack else "",
            office_policy=office_policy,
            legal_checks=legal_checks,
            review_status=review.status,
            site_context=site_context,
        )
    )
    verdict = _final_verdict(steps, quality.risk_level, analysis, review.status)
    confidence = _plan_confidence(steps, quality.risk_level, has_analysis)
    source_log = tuple(
        AgentSourceLog(
            name=trace.name,
            status=trace.status,
            source=trace.source,
            official_data=trace.official_data,
            archon_inference=trace.archon_inference,
            pending_validation=trace.pending_validation,
        )
        for trace in quality.source_traces
    )
    return AgentPlan(
        verdict=verdict,
        verdict_label=_verdict_label(verdict),
        confidence=confidence,
        summary=_summary(verdict, steps, questions, quality.risk_label),
        steps=steps,
        questions=questions,
        source_log=source_log,
    )


def _location_step(
    address: str,
    municipality: str,
    has_coords: bool,
    expediente_status: str,
) -> AgentPlanStep:
    if expediente_status == "geocodificando":
        status = "in_progress"
        inference = "ARCHON está resolviendo la ubicación del expediente."
        action = "Esperar a que termine la resolución automática."
    elif municipality or has_coords:
        status = "completed"
        inference = "La parcela tiene ubicación suficiente para cruzar fuentes."
        action = "Continuar con Catastro y fuentes sectoriales."
    elif address:
        status = "pending"
        inference = "Hay dirección, pero todavía no consta municipio resuelto."
        action = "Resolver parcela antes de emitir dictamen."
    else:
        status = "blocked"
        inference = "No hay dirección, coordenadas ni referencia catastral suficiente."
        action = "Añadir dirección, coordenadas GPS o referencia catastral."
    return AgentPlanStep(
        code="resolve-location",
        title="Resolver parcela",
        intent="Voy a resolver dirección/coordenadas para ubicar el expediente.",
        status=status,
        official_data=municipality or address or "Sin dato de ubicación.",
        archon_inference=inference,
        confidence="alta" if status == "completed" else "baja" if status == "blocked" else "media",
        recommended_action=action,
    )


def _catastro_step(cadastral_ref: str, site_context: dict[str, Any]) -> AgentPlanStep:
    parcel = _loads_dict(site_context.get("parcel_detail"))
    if cadastral_ref or parcel:
        status = "completed"
        official = cadastral_ref or _first(parcel.get("surface_m2"), "Detalle parcelario")
        inference = "Catastro aporta identificación base y datos de parcela."
        action = "Usar referencia y datos catastrales como base del expediente."
    elif site_context:
        status = "needs_review"
        official = "Contexto resuelto sin referencia catastral completa."
        inference = "La parcela está localizada, pero falta referencia catastral fiable."
        action = "Confirmar referencia catastral antes de cerrar informe."
    else:
        status = "pending"
        official = "Catastro pendiente."
        inference = "ARCHON necesita ubicación para consultar Catastro."
        action = "Resolver parcela primero."
    return AgentPlanStep(
        code="query-catastro",
        title="Consultar Catastro",
        intent="Voy a consultar Catastro OVC para identificar la parcela.",
        status=status,
        official_data=str(official),
        archon_inference=inference,
        confidence="alta" if status == "completed" else "media",
        recommended_action=action,
    )


def _sectorial_step(site_context: dict[str, Any]) -> AgentPlanStep:
    source_keys = ("flood_zone", "natura2000", "costas", "carreteras")
    consulted = [key for key in source_keys if site_context.get(key)]
    legal_checks = site_context.get("legal_checks") if site_context else []
    legal_checks = legal_checks if isinstance(legal_checks, list) else []
    statuses = {
        str(check.get("status") or "")
        for check in legal_checks
        if isinstance(check, dict)
    }
    if len(consulted) >= 4 and not ({"missing", "pending_review"} & statuses):
        status = "completed"
    elif site_context and consulted:
        status = "needs_review"
    elif site_context:
        status = "pending"
    else:
        status = "blocked"
    return AgentPlanStep(
        code="sectorial-sources",
        title="Comprobar afecciones",
        intent="Voy a cruzar fuentes sectoriales: SNCZI, Natura 2000, Costas y Carreteras.",
        status=status,
        official_data=f"{len(consulted)}/4 fuentes sectoriales con dato.",
        archon_inference=(
            "El cribado sectorial está completo."
            if status == "completed"
            else "Faltan fuentes o alguna requiere revisión técnica."
        ),
        confidence="alta" if status == "completed" else "media" if site_context else "baja",
        recommended_action=(
            "Revisar advertencias sectoriales en el informe."
            if status == "needs_review"
            else "Completar contexto oficial de parcela."
            if status in {"pending", "blocked"}
            else "Continuar con PGOU y dictamen preliminar."
        ),
    )


def _pgou_step(
    municipality: str,
    site_context: dict[str, Any],
    pack: Any,
    office_policy: MunicipalityPolicy | None,
) -> AgentPlanStep:
    zoning = _loads_dict(site_context.get("parcel_zoning"))
    if pack and pack.status == "validado" and zoning:
        status = "completed"
        inference = "Existe base municipal validada y zonificación preliminar."
    elif pack or zoning:
        status = "needs_review"
        inference = "El PGOU existe en lectura preliminar; falta validación completa."
    elif municipality:
        status = "pending"
        inference = "Hay municipio, pero falta paquete PGOU o zonificación de parcela."
    else:
        status = "blocked"
        inference = "Sin municipio no se puede buscar normativa municipal."
    official = (
        f"{pack.municipality} · {pack.status} · {pack.last_updated}"
        if pack
        else municipality or "Municipio pendiente"
    )
    has_office_pgou = bool(office_policy and office_policy.validated_pgou)
    if has_office_pgou and status != "completed":
        assert office_policy is not None
        inference = (
            f"{inference} El despacho tiene criterio previo validado para "
            f"{office_policy.municipality}; debe reutilizarse con comprobación de "
            "fecha, fuente y alcance."
        )
    return AgentPlanStep(
        code="pgou-normativa",
        title="Buscar normativa PGOU",
        intent="Voy a buscar normativa municipal y zonificación preliminar.",
        status=status,
        official_data=official,
        archon_inference=inference,
        confidence="alta" if status == "completed" else "media" if status != "blocked" else "baja",
        recommended_action=(
            "Confirmar ordenanza exacta en planos/visor municipal."
            if status == "needs_review" and not has_office_pgou
            else "Revisar criterio previo del despacho y confirmar que sigue vigente."
            if status == "needs_review"
            else "Cargar o validar paquete municipal antes del informe."
            if status in {"pending", "blocked"}
            else "Usar PGOU validado como base del dictamen."
        ),
    )


def _plan_document_step(has_plan: bool) -> AgentPlanStep:
    return AgentPlanStep(
        code="plan-document",
        title="Revisar plano adjunto",
        intent="Voy a leer el plano para contrastar el encargo con la normativa.",
        status="completed" if has_plan else "needs_review",
        official_data="Plano adjunto." if has_plan else "Sin plano adjunto.",
        archon_inference=(
            "El análisis puede contrastar documento y parcela."
            if has_plan
            else "Sin plano, el informe queda limitado a Catastro y fuentes oficiales."
        ),
        confidence="alta" if has_plan else "media",
        recommended_action=(
            "Analizar plano con PGOU."
            if has_plan
            else "Preguntar si se continúa sin plano o adjuntar PDF/DWG."
        ),
    )


def _dictamen_step(
    has_analysis: bool,
    has_plan: bool,
    site_context: dict[str, Any],
    analysis: dict[str, Any],
) -> AgentPlanStep:
    if has_analysis:
        verdict = str(analysis.get("verdict") or analysis.get("verdict_label") or "revisar")
        return AgentPlanStep(
            code="preliminary-dictamen",
            title="Generar dictamen preliminar",
            intent="Voy a convertir fuentes y plano en viable / condicionado / revisar.",
            status="completed",
            official_data=f"Dictamen generado: {verdict}.",
            archon_inference=str(analysis.get("summary") or "Análisis generado."),
            confidence="media",
            recommended_action="Revisar flags, próximos pasos y exportar informe.",
        )
    if has_plan or site_context:
        return AgentPlanStep(
            code="preliminary-dictamen",
            title="Generar dictamen preliminar",
            intent="Voy a convertir fuentes y plano en viable / condicionado / revisar.",
            status="pending",
            official_data="Análisis pendiente.",
            archon_inference="ARCHON tiene datos suficientes para preparar un dictamen preliminar.",
            confidence="media",
            recommended_action="Pulsar Ejecutar revisión completa o Analizar con PGOU.",
        )
    return AgentPlanStep(
        code="preliminary-dictamen",
        title="Generar dictamen preliminar",
        intent="Voy a convertir fuentes y plano en viable / condicionado / revisar.",
        status="blocked",
        official_data="Sin fuentes ni plano.",
        archon_inference="No hay base mínima para emitir conclusión responsable.",
        confidence="baja",
        recommended_action="Completar ubicación, Catastro o plano antes de analizar.",
    )


def _architect_review_step(review_status: str, review_label: str) -> AgentPlanStep:
    if review_status == "confirmed":
        status = "completed"
        action = "Mantener revisión firmada en el informe."
    elif review_status in {"needs_correction", "excluded"}:
        status = "needs_review"
        action = "Corregir o excluir conclusiones antes de compartir."
    else:
        status = "needs_review"
        action = "Arquitecto debe confirmar, corregir o anotar el expediente."
    return AgentPlanStep(
        code="architect-review",
        title="Marcar puntos de arquitecto",
        intent="Voy a separar conclusiones automáticas de revisión profesional.",
        status=status,
        official_data=review_label,
        archon_inference="ADV ARCHON actúa como copiloto, no como caja negra.",
        confidence="alta" if status == "completed" else "media",
        recommended_action=action,
    )


def _build_questions(
    *,
    has_plan: bool,
    pack_status: str,
    office_policy: MunicipalityPolicy | None,
    legal_checks: list[Any],
    review_status: str,
    site_context: dict[str, Any],
) -> list[AgentQuestion]:
    questions: list[AgentQuestion] = []
    if not has_plan:
        questions.append(
            AgentQuestion(
                code="continue-without-plan",
                question=(
                    "No tengo plano. ¿Quieres continuar solo con Catastro y "
                    "fuentes oficiales?"
                ),
                reason="El dictamen será más limitado sin contrastar el documento técnico.",
            )
        )
    if pack_status and pack_status != "validado":
        questions.append(
            AgentQuestion(
                code="pgou-preliminar",
                question=(
                    "El PGOU está preliminar. ¿Quieres usar el criterio previo del despacho "
                    "y mantener el informe como no validado?"
                    if office_policy and office_policy.validated_pgou
                    else "El PGOU está preliminar. ¿Quieres marcar el informe como no validado?"
                ),
                reason=(
                    "Hay memoria de despacho, pero la zonificación exacta sigue requiriendo "
                    "plano/visor municipal validado."
                    if office_policy and office_policy.validated_pgou
                    else "La zonificación exacta requiere plano/visor municipal validado."
                ),
            )
        )
    elif not pack_status:
        questions.append(
            AgentQuestion(
                code="pgou-missing",
                question="No hay paquete PGOU validado. ¿Quieres continuar con advertencia?",
                reason="La normativa municipal es una pieza crítica del expediente.",
            )
        )
    statuses = {
        str(check.get("status") or "")
        for check in legal_checks
        if isinstance(check, dict)
    }
    if "conditional" in statuses or _has_sectorial_affection(site_context):
        questions.append(
            AgentQuestion(
                code="sectorial-warning",
                question=(
                    "La parcela tiene afección sectorial. ¿Quieres incluir advertencia "
                    "reforzada?"
                ),
                reason="Las afecciones pueden condicionar licencia, informe o tramitación.",
            )
        )
    if review_status != "confirmed":
        questions.append(
            AgentQuestion(
                code="architect-review",
                question="¿Quieres confirmar, corregir o anotar la revisión del arquitecto?",
                reason="El informe premium debe separar dato oficial e inferencia revisable.",
            )
        )
    return questions[:4]


def _final_verdict(
    steps: tuple[AgentPlanStep, ...],
    risk_level: str,
    analysis: dict[str, Any],
    review_status: str,
) -> str:
    critical_blocked = {
        "resolve-location",
        "query-catastro",
        "sectorial-sources",
        "pgou-normativa",
        "preliminary-dictamen",
    }
    if any(step.status == "blocked" and step.code in critical_blocked for step in steps):
        return "blocked"
    if review_status in {"needs_correction", "excluded"} or risk_level == "alto":
        return "review"
    raw_verdict = str(analysis.get("verdict") or analysis.get("verdict_label") or "")
    normalized = raw_verdict.casefold()
    if normalized in {"no recomendable", "incumple", "rechazar"}:
        return "review"
    if any(step.status == "needs_review" for step in steps) or risk_level == "medio":
        return "conditional"
    return "viable"


def _plan_confidence(
    steps: tuple[AgentPlanStep, ...],
    risk_level: str,
    has_analysis: bool,
) -> str:
    if any(step.status == "blocked" for step in steps) or risk_level == "alto":
        return "baja"
    if not has_analysis or any(step.status == "needs_review" for step in steps):
        return "media"
    return "alta"


def _summary(
    verdict: str,
    steps: tuple[AgentPlanStep, ...],
    questions: tuple[AgentQuestion, ...],
    risk_label: str,
) -> str:
    completed = sum(1 for step in steps if step.status == "completed")
    blocked = sum(1 for step in steps if step.status == "blocked")
    review = sum(1 for step in steps if step.status == "needs_review")
    if verdict == "blocked":
        return (
            f"Expediente bloqueado: {blocked} paso(s) crítico(s) impiden emitir "
            "un dictamen responsable."
        )
    if verdict == "viable":
        return (
            f"Expediente guiado con {completed}/{len(steps)} pasos completados. "
            f"{risk_label}."
        )
    if verdict == "conditional":
        return (
            f"Expediente condicionado: {review} paso(s) requieren decisión o "
            f"validación. Preguntas abiertas: {len(questions)}."
        )
    return (
        f"Expediente para revisar: {review} paso(s) necesitan criterio técnico. "
        f"{risk_label}."
    )


def _verdict_label(verdict: str) -> str:
    return {
        "viable": "Viable",
        "conditional": "Condicionado",
        "review": "Revisar",
        "blocked": "Bloqueado",
    }.get(verdict, "Revisar")


def _has_sectorial_affection(site_context: dict[str, Any]) -> bool:
    flood = _loads_dict(site_context.get("flood_zone"))
    natura = _loads_dict(site_context.get("natura2000"))
    costas = _loads_dict(site_context.get("costas"))
    roads = _loads_dict(site_context.get("carreteras"))
    return any(
        (
            flood.get("in_flood_zone") is True,
            natura.get("in_protected_area") is True,
            costas.get("in_public_domain") is True,
            costas.get("in_protection_servitude") is True,
            roads.get("in_affection_zone") is True,
        )
    )


def _apply_history_overlay(
    steps: tuple[AgentPlanStep, ...],
    history: tuple[AgentRunEvent, ...],
) -> tuple[AgentPlanStep, ...]:
    latest_by_step: dict[str, AgentRunEvent] = {}
    for event in history:
        latest_by_step[event.step_code] = event
    updated: list[AgentPlanStep] = []
    for step in steps:
        latest_event = latest_by_step.get(step.code)
        if latest_event and latest_event.status == "in_progress":
            updated.append(
                replace(
                    step,
                    status="in_progress",
                    archon_inference=latest_event.message or step.archon_inference,
                    recommended_action=latest_event.message or step.recommended_action,
                )
            )
        elif latest_event and latest_event.status == "blocked" and step.status != "completed":
            updated.append(
                replace(
                    step,
                    status="blocked",
                    archon_inference=latest_event.message or step.archon_inference,
                    recommended_action=latest_event.message or step.recommended_action,
                )
            )
        else:
            updated.append(step)
    return tuple(updated)


def _apply_step_reviews(
    steps: tuple[AgentPlanStep, ...],
    reviews: dict[str, AgentStepReview],
) -> tuple[AgentPlanStep, ...]:
    if not reviews:
        return steps
    updated: list[AgentPlanStep] = []
    for step in steps:
        review = reviews.get(step.code)
        if review is None:
            updated.append(step)
            continue
        status = step.status
        action = step.recommended_action
        inference = step.archon_inference
        if review.status in {"validated", "accepted_warning"} and step.status != "blocked":
            status = "completed"
            action = review.label
            inference = f"{step.archon_inference} Decisión arquitecto: {review.label}."
        elif review.status == "requested_repeat":
            status = "pending" if step.status != "blocked" else step.status
            action = "Repetir consulta o refrescar este paso del agente."
        elif review.status == "excluded":
            action = "Excluido del informe por decisión del arquitecto."
        elif review.status == "included":
            action = "Incluido expresamente en el informe."
        updated.append(
            replace(
                step,
                status=status,
                archon_inference=inference,
                recommended_action=action,
                review_status=review.status,
                review_label=review.label,
                review_note=review.note,
                include_in_report=review.include_in_report,
            )
        )
    return tuple(updated)


def _review_status_from_action(action: str) -> str:
    normalized = action.strip().replace("-", "_")
    return {
        "validate": "validated",
        "validated": "validated",
        "accept_warning": "accepted_warning",
        "accepted_warning": "accepted_warning",
        "include": "included",
        "included": "included",
        "exclude": "excluded",
        "excluded": "excluded",
        "repeat": "requested_repeat",
        "requested_repeat": "requested_repeat",
    }.get(normalized, "pending")


def _review_include_from_action(
    action: str,
    previous: AgentStepReview | None,
) -> bool:
    normalized = action.strip().replace("-", "_")
    if normalized in {"exclude", "excluded"}:
        return False
    if normalized in {"include", "included"}:
        return True
    if previous is not None:
        return previous.include_in_report
    return True


def _loads_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _first(*values: object) -> object:
    for value in values:
        if value:
            return value
    return "Dato no disponible"


__all__ = [
    "AGENT_STEP_STATUS_LABELS",
    "AGENT_STEP_REVIEW_LABELS",
    "AgentPlan",
    "AgentPlanStep",
    "AgentQuestion",
    "AgentRunEvent",
    "AgentStepReview",
    "AgentSourceLog",
    "append_agent_event",
    "build_expediente_agent_plan",
    "load_agent_history",
    "load_agent_step_reviews",
    "update_agent_step_review",
]
