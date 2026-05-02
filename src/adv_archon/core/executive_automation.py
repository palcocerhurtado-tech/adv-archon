from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from adv_archon.core.tasks import LaunchAgentRecord, TaskRecord, TaskStore


def _normalize_label_fragment(value: str) -> str:
    text = value.strip().lower().replace(" ", "-").replace("_", "-")
    return "".join(character for character in text if character.isalnum() or character == "-")


@dataclass(slots=True, frozen=True)
class ClockTime:
    hour: int
    minute: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.hour <= 23:
            raise ValueError("La hora debe estar entre 0 y 23.")
        if not 0 <= self.minute <= 59:
            raise ValueError("Los minutos deben estar entre 0 y 59.")

    @classmethod
    def parse(cls, value: str) -> ClockTime:
        try:
            hour_text, minute_text = value.strip().split(":", maxsplit=1)
        except ValueError as exc:
            raise ValueError(f"Formato de hora inválido: {value}") from exc
        return cls(hour=int(hour_text), minute=int(minute_text))

    def to_calendar_entry(self) -> dict[str, int]:
        return {"Hour": self.hour, "Minute": self.minute}

    def next_due_text(self, *, reference: datetime, timezone_name: str) -> str:
        localized = reference.astimezone(ZoneInfo(timezone_name))
        candidate = localized.replace(
            hour=self.hour,
            minute=self.minute,
            second=0,
            microsecond=0,
        )
        if candidate <= localized:
            candidate += timedelta(days=1)
        return candidate.strftime("%Y-%m-%d %H:%M")

    def render(self) -> str:
        return f"{self.hour:02d}:{self.minute:02d}"


@dataclass(slots=True, frozen=True)
class LaunchdWorkflowSpec:
    key: str
    title: str
    description: str
    prompt: str
    times: tuple[ClockTime, ...] = ()
    interval_minutes: int | None = None
    run_at_load: bool = True

    def schedule_payload(self) -> dict[str, Any]:
        if self.interval_minutes is not None:
            return {"start_interval": self.interval_minutes * 60}
        return {
            "start_calendar_interval": tuple(time.to_calendar_entry() for time in self.times)
        }


@dataclass(slots=True, frozen=True)
class PersistentTaskTemplate:
    key: str
    title: str
    prompt: str
    time: ClockTime
    recurrence: str
    category: str
    metadata: dict[str, Any] | None = None

    def due_text(self, *, reference: datetime, timezone_name: str) -> str:
        return self.time.next_due_text(reference=reference, timezone_name=timezone_name)


@dataclass(slots=True, frozen=True)
class ExecutiveAutomationBundle:
    key: str
    name: str
    description: str
    launch_workflows: tuple[LaunchdWorkflowSpec, ...]
    task_templates: tuple[PersistentTaskTemplate, ...]


@dataclass(slots=True, frozen=True)
class InstalledExecutiveAutomation:
    bundle: ExecutiveAutomationBundle
    launch_agents: tuple[LaunchAgentRecord, ...]
    tasks: tuple[TaskRecord, ...]


def build_executive_automation_bundle(
    *,
    morning_time: ClockTime | str | None = None,
    triage_times: tuple[ClockTime | str, ...] | None = None,
    study_time: ClockTime | str | None = None,
    nightly_review_time: ClockTime | str | None = None,
    study_focus: str = "tu linea actual de estudio",
    meeting_prep_window_minutes: int = 45,
    meeting_prep_poll_minutes: int = 15,
) -> ExecutiveAutomationBundle:
    morning = _coerce_clock_time(morning_time or ClockTime(8, 0))
    triage = tuple(
        _coerce_clock_time(item)
        for item in (
            triage_times
            or (
                ClockTime(9, 0),
                ClockTime(14, 0),
                ClockTime(18, 0),
            )
        )
    )
    study = _coerce_clock_time(study_time or ClockTime(19, 30))
    nightly = _coerce_clock_time(nightly_review_time or ClockTime(21, 30))
    clean_focus = study_focus.strip() or "tu linea actual de estudio"

    launch_workflows = (
        LaunchdWorkflowSpec(
            key="morning_briefing",
            title="Briefing ejecutivo de la mañana",
            description="Genera un briefing automático con agenda, inbox y prioridades.",
            prompt=(
                "Dame un briefing ejecutivo del dia con agenda, inbox, prioridades, "
                "reuniones relevantes y bloqueos abiertos."
            ),
            times=(morning,),
        ),
        LaunchdWorkflowSpec(
            key="meeting_prep",
            title="Preparacion previa de reuniones",
            description="Revisa cada cierto tiempo si hay reuniones proximas y prepara contexto.",
            prompt=(
                f"Revisa si tengo reuniones en los proximos {meeting_prep_window_minutes} minutos. "
                "Si las hay, preparame el briefing de la mas proxima con agenda, correos, notas y "
                "documentos relevantes. Si no las hay, responde brevemente que no toca prep."
            ),
            interval_minutes=meeting_prep_poll_minutes,
        ),
        LaunchdWorkflowSpec(
            key="gmail_triage",
            title="Triage de Gmail",
            description="Clasifica el inbox y detecta respuestas del dia.",
            prompt=(
                "Hazme triage del Gmail. Dime que correos requieren respuesta hoy, "
                "cuales pueden esperar y propon borradores breves para los mas urgentes."
            ),
            times=triage,
        ),
        LaunchdWorkflowSpec(
            key="nightly_review",
            title="Revision nocturna",
            description="Cierra el dia revisando pendientes y preparando manana.",
            prompt=(
                "Haz una revision nocturna de pendientes. Resume bloqueos, tareas abiertas, "
                "agenda de manana y tres prioridades para arrancar bien."
            ),
            times=(nightly,),
        ),
    )
    task_templates = (
        PersistentTaskTemplate(
            key="study_review",
            title=f"Bloque de estudio | {clean_focus}",
            prompt=(
                f"Recordatorio de estudio sobre {clean_focus}. "
                "Incluye resumen breve, tres preguntas de repaso y el siguiente paso recomendado."
            ),
            time=study,
            recurrence="daily",
            category="study",
            metadata={"focus": clean_focus, "kind": "study_review"},
        ),
    )
    return ExecutiveAutomationBundle(
        key="executive_assistant",
        name="Executive Assistant",
        description=(
            "Automatizaciones ejecutivas locales para briefing diario, preparacion de reuniones, "
            "triage de Gmail, estudio y revision nocturna."
        ),
        launch_workflows=launch_workflows,
        task_templates=task_templates,
    )


def list_executive_automation_presets() -> list[dict[str, Any]]:
    bundle = build_executive_automation_bundle()
    return [
        {
            "bundle_key": bundle.key,
            "name": bundle.name,
            "description": bundle.description,
            "launch_workflows": [
                {
                    "key": workflow.key,
                    "title": workflow.title,
                    "description": workflow.description,
                    "times": [time.render() for time in workflow.times],
                    "interval_minutes": workflow.interval_minutes,
                }
                for workflow in bundle.launch_workflows
            ],
            "task_templates": [
                {
                    "key": template.key,
                    "title": template.title,
                    "category": template.category,
                    "time": template.time.render(),
                    "recurrence": template.recurrence,
                }
                for template in bundle.task_templates
            ],
        }
    ]


def install_executive_automation(
    *,
    store: TaskStore,
    adv_command: str,
    bundle: ExecutiveAutomationBundle | None = None,
    timezone_name: str = "Europe/Madrid",
    launch_agents_dir: Path | None = None,
    logs_dir: Path | None = None,
    working_directory: Path | None = None,
    reference_time: datetime | None = None,
    load_launch_agents: bool = True,
) -> InstalledExecutiveAutomation:
    active_bundle = bundle or build_executive_automation_bundle()
    now = reference_time or datetime.now(UTC)
    automation_logs_dir = logs_dir or (Path.home() / ".adv-archon" / "logs" / "automation")
    records: list[LaunchAgentRecord] = []
    tasks: list[TaskRecord] = []

    for workflow in active_bundle.launch_workflows:
        suffix = _normalize_label_fragment(f"{active_bundle.key}-{workflow.key}")
        label = f"com.adv-archon.{suffix}"
        stdout_path = automation_logs_dir / f"{suffix}.out.log"
        stderr_path = automation_logs_dir / f"{suffix}.err.log"
        schedule = workflow.schedule_payload()
        records.append(
            store.install_named_launch_agent(
                label=label,
                program_arguments=[adv_command, workflow.prompt],
                start_interval=schedule.get("start_interval"),
                start_calendar_interval=schedule.get("start_calendar_interval"),
                run_at_load=workflow.run_at_load,
                launch_agents_dir=launch_agents_dir,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                working_directory=working_directory,
                load=load_launch_agents,
            )
        )

    for template in active_bundle.task_templates:
        source = f"automation:{active_bundle.key}:{template.key}"
        task_metadata = {
            "bundle": active_bundle.key,
            "preset": template.key,
            **(template.metadata or {}),
        }
        tasks.append(
            store.upsert_task(
                title=template.title,
                due_text=template.due_text(reference=now, timezone_name=timezone_name),
                prompt=template.prompt,
                recurrence=template.recurrence,
                category=template.category,
                source=source,
                metadata=task_metadata,
            )
        )

    return InstalledExecutiveAutomation(
        bundle=active_bundle,
        launch_agents=tuple(records),
        tasks=tuple(tasks),
    )


def _coerce_clock_time(value: ClockTime | str) -> ClockTime:
    if isinstance(value, ClockTime):
        return value
    return ClockTime.parse(value)
