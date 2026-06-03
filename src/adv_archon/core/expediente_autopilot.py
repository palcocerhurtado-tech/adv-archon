from __future__ import annotations

import json
import sqlite3
import uuid
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from adv_archon.core.agent_plan import (
    AgentQuestion,
    AgentRunEvent,
    append_agent_event,
    build_expediente_agent_plan,
    load_agent_history,
)
from adv_archon.core.expediente_quality import evaluate_expediente_quality

PERMISSION_AUTOMATIC = "automatic"
PERMISSION_CONFIRM = "requires_confirmation"
PERMISSION_BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class AutopilotSignal:
    code: str
    label: str
    status: str
    detail: str

    def as_payload(self) -> dict[str, str]:
        return {
            "code": self.code,
            "label": self.label,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class AutopilotTask:
    code: str
    title: str
    status: str
    permission: str
    source: str
    evidence: str
    result: str
    next_action: str
    step_code: str = ""
    question: str = ""

    @property
    def permission_label(self) -> str:
        return {
            PERMISSION_AUTOMATIC: "Automático",
            PERMISSION_CONFIRM: "Requiere confirmación",
            PERMISSION_BLOCKED: "Bloqueado",
        }.get(self.permission, self.permission)

    @property
    def status_label(self) -> str:
        return {
            "pending": "Pendiente",
            "in_progress": "En curso",
            "completed": "Completado",
            "needs_review": "Necesita revisión",
            "blocked": "Bloqueado",
        }.get(self.status, self.status)

    def as_payload(self) -> dict[str, str]:
        return {
            "code": self.code,
            "title": self.title,
            "status": self.status,
            "status_label": self.status_label,
            "permission": self.permission,
            "permission_label": self.permission_label,
            "source": self.source,
            "evidence": self.evidence,
            "result": self.result,
            "next_action": self.next_action,
            "step_code": self.step_code,
            "question": self.question,
        }


@dataclass(frozen=True, slots=True)
class ArchitectInboxItem:
    code: str
    title: str
    severity: str
    action: str
    reason: str
    step_code: str = ""

    def as_payload(self) -> dict[str, str]:
        return {
            "code": self.code,
            "title": self.title,
            "severity": self.severity,
            "action": self.action,
            "reason": self.reason,
            "step_code": self.step_code,
        }


@dataclass(frozen=True, slots=True)
class PermissionRule:
    level: str
    label: str
    examples: tuple[str, ...]

    def as_payload(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "label": self.label,
            "examples": list(self.examples),
        }


@dataclass(frozen=True, slots=True)
class OfficeMemory:
    municipalities: tuple[str, ...]
    recurring_warnings: tuple[str, ...]
    validated_decisions: int
    preferred_report_style: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "municipalities": list(self.municipalities),
            "recurring_warnings": list(self.recurring_warnings),
            "validated_decisions": self.validated_decisions,
            "preferred_report_style": self.preferred_report_style,
        }


@dataclass(frozen=True, slots=True)
class ExpedienteAutopilot:
    expediente_id: str
    expediente_title: str
    verdict: str
    verdict_label: str
    summary: str
    current_step: str
    progress_percent: int
    signals: tuple[AutopilotSignal, ...]
    tasks: tuple[AutopilotTask, ...]
    inbox: tuple[ArchitectInboxItem, ...]
    questions: tuple[AgentQuestion, ...]
    permissions: tuple[PermissionRule, ...]
    office_memory: OfficeMemory
    recent_events: tuple[AgentRunEvent, ...]

    @property
    def next_task(self) -> AutopilotTask | None:
        for task in self.tasks:
            if task.status != "completed":
                return task
        return None

    @property
    def is_ready_for_report(self) -> bool:
        return self.verdict != "blocked" and not any(
            item.severity == "high" for item in self.inbox
        )

    def as_payload(self) -> dict[str, Any]:
        return {
            "expediente_id": self.expediente_id,
            "expediente_title": self.expediente_title,
            "verdict": self.verdict,
            "verdict_label": self.verdict_label,
            "summary": self.summary,
            "current_step": self.current_step,
            "progress_percent": self.progress_percent,
            "signals": [signal.as_payload() for signal in self.signals],
            "tasks": [task.as_payload() for task in self.tasks],
            "inbox": [item.as_payload() for item in self.inbox],
            "questions": [question.as_payload() for question in self.questions],
            "permissions": [rule.as_payload() for rule in self.permissions],
            "office_memory": self.office_memory.as_payload(),
            "recent_events": [event.as_payload() for event in self.recent_events],
            "ready_for_report": self.is_ready_for_report,
        }


@dataclass(frozen=True, slots=True)
class AutopilotRunRecord:
    id: str
    expediente_id: str
    summary: str
    payload: dict[str, Any]
    created_at: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "expediente_id": self.expediente_id,
            "summary": self.summary,
            "payload": self.payload,
            "created_at": self.created_at,
        }


class AutopilotStore:
    """Persist Autopilot objectives without changing ExpedienteStore schema."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS autopilot_runs (
                id TEXT PRIMARY KEY,
                expediente_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_autopilot_runs_expediente_created
            ON autopilot_runs(expediente_id, created_at DESC)
            """
        )
        self._conn.commit()

    def save_run(
        self,
        autopilot: ExpedienteAutopilot,
        *,
        run_id: str | None = None,
    ) -> AutopilotRunRecord:
        created_at = datetime.now(UTC).isoformat(timespec="seconds")
        record = AutopilotRunRecord(
            id=run_id or str(uuid.uuid4()),
            expediente_id=autopilot.expediente_id,
            summary=autopilot.summary,
            payload=autopilot.as_payload(),
            created_at=created_at,
        )
        self._conn.execute(
            """
            INSERT OR REPLACE INTO autopilot_runs
              (id, expediente_id, summary, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.expediente_id,
                record.summary,
                json.dumps(record.payload, ensure_ascii=False),
                record.created_at,
            ),
        )
        self._conn.commit()
        return record

    def latest(self, expediente_id: str) -> AutopilotRunRecord | None:
        row = self._conn.execute(
            """
            SELECT * FROM autopilot_runs
            WHERE expediente_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (expediente_id,),
        ).fetchone()
        return self._row_to_record(row) if row else None

    def list_for_expediente(
        self,
        expediente_id: str,
        *,
        limit: int = 20,
    ) -> list[AutopilotRunRecord]:
        rows = self._conn.execute(
            """
            SELECT * FROM autopilot_runs
            WHERE expediente_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (expediente_id, max(1, limit)),
        ).fetchall()
        return [self._row_to_record(row) for row in rows]

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> AutopilotRunRecord:
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, ValueError):
            payload = {}
        return AutopilotRunRecord(
            id=row["id"],
            expediente_id=row["expediente_id"],
            summary=row["summary"],
            payload=payload if isinstance(payload, dict) else {},
            created_at=row["created_at"],
        )


def build_expediente_autopilot(
    expediente: Any,
    *,
    office_expedientes: Iterable[Any] = (),
) -> ExpedienteAutopilot:
    """Build the local-first Autopilot view for one expediente.

    Autopilot deliberately derives state from existing expediente fields,
    agent_plan and quality checks. It does not invent a second workflow store:
    execution remains visible through the persistent agent history.
    """
    plan = build_expediente_agent_plan(expediente)
    quality = evaluate_expediente_quality(expediente)
    site_context = _loads_dict(getattr(expediente, "site_context", ""))
    history = load_agent_history(getattr(expediente, "agent_history", ""))
    signals = _build_signals(expediente, site_context, plan.questions, quality)
    tasks = _build_tasks(expediente, plan.steps, quality)
    inbox = _build_inbox(expediente, plan.questions, tasks, quality)
    completed = sum(1 for task in tasks if task.status == "completed")
    progress = int((completed / len(tasks)) * 100) if tasks else 0
    next_task = next((task for task in tasks if task.status != "completed"), None)
    current_step = next_task.title if next_task else "Expediente listo para revisión final"
    return ExpedienteAutopilot(
        expediente_id=str(getattr(expediente, "id", "")),
        expediente_title=str(getattr(expediente, "title", "") or "Expediente"),
        verdict=plan.verdict,
        verdict_label=plan.verdict_label,
        summary=_autopilot_summary(plan.verdict_label, progress, inbox),
        current_step=current_step,
        progress_percent=progress,
        signals=tuple(signals),
        tasks=tuple(tasks),
        inbox=tuple(inbox),
        questions=plan.questions,
        permissions=_permission_rules(),
        office_memory=build_office_memory(office_expedientes),
        recent_events=history[-8:],
    )


def build_office_memory(expedientes: Iterable[Any]) -> OfficeMemory:
    municipalities: Counter[str] = Counter()
    warnings: Counter[str] = Counter()
    validated = 0
    for exp in expedientes:
        municipality = str(getattr(exp, "municipality", "") or "").strip()
        if municipality:
            municipalities[municipality] += 1
        site_context = _loads_dict(getattr(exp, "site_context", ""))
        checks = site_context.get("legal_checks") if site_context else []
        if isinstance(checks, list):
            for check in checks:
                if not isinstance(check, dict):
                    continue
                status = str(check.get("status") or "")
                if status in {"conditional", "pending_review", "missing"}:
                    title = str(check.get("title") or check.get("id") or "Advertencia")
                    warnings[title] += 1
        try:
            reviews = json.loads(str(getattr(exp, "agent_step_reviews", "") or "{}"))
        except (TypeError, ValueError):
            reviews = {}
        if isinstance(reviews, dict):
            validated += sum(
                1
                for item in reviews.values()
                if isinstance(item, dict)
                and str(item.get("status") or "")
                in {"validated", "accepted_warning", "included"}
            )
    return OfficeMemory(
        municipalities=tuple(name for name, _ in municipalities.most_common(5)),
        recurring_warnings=tuple(name for name, _ in warnings.most_common(5)),
        validated_decisions=validated,
        preferred_report_style=(
            "Informe preliminar de viabilidad urbanística con trazabilidad fuerte."
        ),
    )


def append_autopilot_checkpoint(
    raw_history: str | list[dict[str, Any]] | tuple[AgentRunEvent, ...] | None,
    autopilot: ExpedienteAutopilot,
    *,
    run_id: str = "",
) -> str:
    next_task = autopilot.next_task
    next_label = next_task.title if next_task else "revisión profesional final"
    return append_agent_event(
        raw_history,
        step_code="autopilot-objectives",
        title="Autopilot de expediente",
        status="in_progress" if next_task else "completed",
        message=(
            f"Autopilot iniciado: {autopilot.progress_percent}% completado; "
            f"próximo paso: {next_label}; bandeja arquitecto: {len(autopilot.inbox)}."
        ),
        run_id=run_id,
    )


def _build_signals(
    expediente: Any,
    site_context: dict[str, Any],
    questions: tuple[AgentQuestion, ...],
    quality: Any,
) -> list[AutopilotSignal]:
    plan_path = str(getattr(expediente, "plan_path", "") or "").strip()
    cadastral = str(getattr(expediente, "cadastral_ref", "") or "").strip() or str(
        site_context.get("cadastral_ref") or ""
    ).strip()
    pack = quality.normative_pack
    sectorial_complete = _sectorial_sources_complete(site_context)
    pending_reviews = sum(1 for issue in quality.missing_items if issue.severity)
    return [
        AutopilotSignal(
            "plan",
            "Plano",
            "ok" if plan_path else "missing",
            "Plano adjunto." if plan_path else "Falta plano; el dictamen queda limitado.",
        ),
        AutopilotSignal(
            "cadastral-ref",
            "Referencia catastral",
            "ok" if cadastral else "missing",
            cadastral or "No consta referencia catastral fiable.",
        ),
        AutopilotSignal(
            "pgou",
            "PGOU municipal",
            "ok" if pack and pack.status == "validado" else "needs_review",
            (
                f"{pack.municipality} · {pack.status} · {pack.last_updated}"
                if pack
                else "Municipio sin paquete normativo validado."
            ),
        ),
        AutopilotSignal(
            "sectorial",
            "Fuentes sectoriales",
            "ok" if sectorial_complete else "needs_review",
            "SNCZI, Natura 2000, Costas y Carreteras completas."
            if sectorial_complete
            else "Falta alguna fuente sectorial o requiere revisión.",
        ),
        AutopilotSignal(
            "architect-review",
            "Pasos sin validar",
            "ok" if not questions and pending_reviews == 0 else "needs_review",
            (
                "No hay preguntas abiertas."
                if not questions and pending_reviews == 0
                else f"{len(questions)} pregunta(s) abiertas; {pending_reviews} alerta(s)."
            ),
        ),
        AutopilotSignal(
            "report",
            "Informe",
            "ok" if getattr(expediente, "report_path", "") else "pending",
            "Informe PDF generado."
            if getattr(expediente, "report_path", "")
            else "Informe pendiente de preparar/exportar.",
        ),
    ]


def _build_tasks(
    expediente: Any,
    steps: tuple[Any, ...],
    quality: Any,
) -> list[AutopilotTask]:
    step_map = {step.code: step for step in steps}
    has_quality_score = getattr(expediente, "quality_score", None) is not None
    has_report = bool(getattr(expediente, "report_path", ""))
    tasks = [
        _task_from_step(
            step_map.get("resolve-location"),
            code="resolve-location",
            title="Resolver ubicación/parcela",
            permission=PERMISSION_AUTOMATIC,
            source="Nominatim + Catastro OVC",
        ),
        _task_from_step(
            step_map.get("query-catastro"),
            code="query-catastro",
            title="Consultar Catastro",
            permission=PERMISSION_AUTOMATIC,
            source="Catastro OVC",
        ),
        _task_from_step(
            step_map.get("sectorial-sources"),
            code="sectorial-sources",
            title="Comprobar afecciones sectoriales",
            permission=PERMISSION_AUTOMATIC,
            source="SNCZI, Red Natura 2000, SIGCOSTAS, CNIG/IDEE",
        ),
        _task_from_step(
            step_map.get("pgou-normativa"),
            code="pgou-normativa",
            title="Buscar normativa PGOU",
            permission=(
                PERMISSION_AUTOMATIC
                if quality.normative_pack and quality.normative_pack.status == "validado"
                else PERMISSION_CONFIRM
            ),
            source="Biblioteca PGOU local + zonificación preliminar",
            question="Confirmar que el PGOU preliminar no se presenta como validado.",
        ),
        _task_from_step(
            step_map.get("plan-document"),
            code="plan-document",
            title="Revisar plano adjunto",
            permission=(
                PERMISSION_AUTOMATIC
                if getattr(expediente, "plan_path", "")
                else PERMISSION_CONFIRM
            ),
            source="Plano/PDF/DWG aportado por el despacho",
            question="No tengo plano. ¿Quieres continuar solo con Catastro y fuentes oficiales?",
        ),
        _task_from_step(
            step_map.get("preliminary-dictamen"),
            code="preliminary-dictamen",
            title="Generar dictamen preliminar",
            permission=PERMISSION_AUTOMATIC,
            source="Contexto oficial + checklist PGOU + análisis local",
        ),
        AutopilotTask(
            code="quality-judge",
            title="Pasar control de calidad local",
            status="completed" if has_quality_score else "pending",
            permission=PERMISSION_AUTOMATIC,
            source="LLM-as-Judge local / reglas de calidad",
            evidence=_quality_evidence(expediente),
            result=_quality_result(expediente),
            next_action=(
                "Usar puntuación de calidad para decidir revisión."
                if has_quality_score
                else "Evaluar el dictamen cuando exista análisis generado."
            ),
            step_code="quality-judge",
        ),
        AutopilotTask(
            code="prepare-report",
            title="Preparar informe PDF",
            status=_report_task_status(expediente),
            permission=PERMISSION_CONFIRM,
            source="Generador PDF local",
            evidence="Informe existente." if has_report else "Informe no exportado.",
            result="PDF listo." if has_report else "Pendiente de exportación.",
            next_action="Exportar solo tras revisar advertencias y límites jurídicos.",
            step_code="prepare-report",
            question="¿Quieres exportar el informe con las advertencias actuales?",
        ),
        _task_from_step(
            step_map.get("architect-review"),
            code="architect-review",
            title="Pedir revisión humana",
            permission=PERMISSION_CONFIRM,
            source="Arquitecto responsable",
        ),
    ]
    return tasks


def _task_from_step(
    step: Any,
    *,
    code: str,
    title: str,
    permission: str,
    source: str,
    question: str = "",
) -> AutopilotTask:
    if step is None:
        return AutopilotTask(
            code=code,
            title=title,
            status="pending",
            permission=permission,
            source=source,
            evidence="Paso pendiente.",
            result="Sin resultado todavía.",
            next_action="Ejecutar Autopilot de expediente.",
            step_code=code,
            question=question,
        )
    return AutopilotTask(
        code=code,
        title=title,
        status=str(getattr(step, "status", "pending")),
        permission=permission,
        source=source,
        evidence=str(getattr(step, "official_data", "")),
        result=str(getattr(step, "archon_inference", "")),
        next_action=str(getattr(step, "recommended_action", "")),
        step_code=str(getattr(step, "code", code)),
        question=question,
    )


def _build_inbox(
    expediente: Any,
    questions: tuple[AgentQuestion, ...],
    tasks: list[AutopilotTask],
    quality: Any,
) -> list[ArchitectInboxItem]:
    inbox: list[ArchitectInboxItem] = []
    if not getattr(expediente, "plan_path", ""):
        inbox.append(
            ArchitectInboxItem(
                code="attach-plan",
                title="Adjuntar plano",
                severity="medium",
                action="Adjuntar plano antes de análisis completo o continuar con advertencia.",
                reason="Sin plano, ARCHON no puede contrastar el documento técnico.",
                step_code="plan-document",
            )
        )
    if quality.normative_pack is None or quality.normative_pack.status != "validado":
        inbox.append(
            ArchitectInboxItem(
                code="confirm-pgou",
                title="Confirmar ordenanza PGOU",
                severity="high" if quality.normative_pack is None else "medium",
                action="Validar fuente municipal, visor o plano de ordenación.",
                reason="ARCHON no debe dar por validada una base preliminar.",
                step_code="pgou-normativa",
            )
        )
    for task in tasks:
        if task.status in {"blocked", "needs_review"} and task.code not in {
            "plan-document",
            "pgou-normativa",
        }:
            inbox.append(
                ArchitectInboxItem(
                    code=f"review-{task.code}",
                    title=task.title,
                    severity="high" if task.status == "blocked" else "medium",
                    action=task.next_action,
                    reason=task.result,
                    step_code=task.step_code,
                )
            )
    for question in questions:
        inbox.append(
            ArchitectInboxItem(
                code=question.code,
                title=question.question,
                severity="medium",
                action="Responder antes de cerrar informe.",
                reason=question.reason,
            )
        )
    return _dedupe_inbox(inbox)[:8]


def _permission_rules() -> tuple[PermissionRule, ...]:
    return (
        PermissionRule(
            PERMISSION_AUTOMATIC,
            "Automático",
            (
                "Consultar fuentes oficiales",
                "Detectar datos faltantes",
                "Preparar resumen técnico",
            ),
        ),
        PermissionRule(
            PERMISSION_CONFIRM,
            "Requiere confirmación",
            (
                "Exportar informe",
                "Marcar PGOU como validado",
                "Aceptar o excluir advertencias",
            ),
        ),
        PermissionRule(
            PERMISSION_BLOCKED,
            "Bloqueado",
            (
                "Inventar normativa",
                "Ocultar afecciones sectoriales",
                "Presentar una inferencia como dato oficial",
            ),
        ),
    )


def _sectorial_sources_complete(site_context: dict[str, Any]) -> bool:
    return all(
        site_context.get(key)
        for key in ("flood_zone", "natura2000", "costas", "carreteras")
    )


def _report_task_status(expediente: Any) -> str:
    if getattr(expediente, "report_path", ""):
        return "completed"
    if getattr(expediente, "analysis_result", ""):
        return "pending"
    return "blocked"


def _quality_evidence(expediente: Any) -> str:
    score = getattr(expediente, "quality_score", None)
    return f"Score {score}/100." if score is not None else "Score no calculado."


def _quality_result(expediente: Any) -> str:
    raw = str(getattr(expediente, "quality_result", "") or "")
    if not raw:
        return "Pendiente de judge local."
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return "Judge local ejecutado; resultado no estructurado."
    verdict = parsed.get("verdict") if isinstance(parsed, dict) else ""
    return f"Judge local: {verdict or 'resultado disponible'}."


def _autopilot_summary(
    verdict_label: str,
    progress: int,
    inbox: list[ArchitectInboxItem],
) -> str:
    high = sum(1 for item in inbox if item.severity == "high")
    medium = sum(1 for item in inbox if item.severity == "medium")
    if high:
        return (
            f"Autopilot detecta {high} bloqueo(s) técnico(s). "
            f"Resultado actual: {verdict_label}. Progreso {progress}%."
        )
    if medium:
        return (
            f"Autopilot puede avanzar, pero deja {medium} decisión(es) para arquitecto. "
            f"Resultado actual: {verdict_label}. Progreso {progress}%."
        )
    return (
        "Autopilot sin bloqueos relevantes. "
        f"Resultado actual: {verdict_label}. Progreso {progress}%."
    )


def _dedupe_inbox(items: list[ArchitectInboxItem]) -> list[ArchitectInboxItem]:
    seen: set[str] = set()
    result: list[ArchitectInboxItem] = []
    for item in items:
        if item.code in seen:
            continue
        seen.add(item.code)
        result.append(item)
    return result


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


__all__ = [
    "PERMISSION_AUTOMATIC",
    "PERMISSION_BLOCKED",
    "PERMISSION_CONFIRM",
    "ArchitectInboxItem",
    "AutopilotSignal",
    "AutopilotStore",
    "AutopilotTask",
    "AutopilotRunRecord",
    "ExpedienteAutopilot",
    "OfficeMemory",
    "PermissionRule",
    "append_autopilot_checkpoint",
    "build_expediente_autopilot",
    "build_office_memory",
]
