from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from adv_archon.core.context import RuntimeContext, capture_runtime_context
from adv_archon.core.knowledge import KnowledgeRecord, KnowledgeStatus, KnowledgeStore
from adv_archon.core.logging import LogEntry, read_log_entries
from adv_archon.core.memory import MemoryRecord, MemoryStore
from adv_archon.core.tasks import TaskRecord, TaskStore

DEFAULT_DAILY_GMAIL_QUERY = "in:inbox category:primary newer_than:14d"
DEFAULT_DAILY_LIMIT = 5


@dataclass(slots=True)
class DailyActivity:
    total_sessions: int
    llm_calls: int
    shell_commands: int
    python_execs: int
    memory_updates: int
    recent_events: list[str]


@dataclass(slots=True)
class DailyReport:
    generated_at: datetime
    context: RuntimeContext
    activity: DailyActivity
    pending_notes: list[MemoryRecord]
    scheduled_tasks: list[TaskRecord]

    def render(self) -> str:
        lines = [
            f"ADV ARCHON daily raw | {self.generated_at:%Y-%m-%d %H:%M}",
            "",
            "Resumen del día:",
            f"- sesiones iniciadas: {self.activity.total_sessions}",
            f"- llamadas LLM: {self.activity.llm_calls}",
            f"- comandos shell: {self.activity.shell_commands}",
            f"- snippets Python: {self.activity.python_execs}",
            f"- cambios en memoria: {self.activity.memory_updates}",
        ]
        if self.activity.recent_events:
            lines.append("Eventos recientes:")
            lines.extend(f"- {event}" for event in self.activity.recent_events)

        lines.extend(
            [
                "",
                "Notas pendientes:",
            ]
        )
        if self.pending_notes:
            lines.extend(_render_note_lines(self.pending_notes))
        else:
            lines.append("- No hay notas pendientes detectadas.")

        lines.extend(
            [
                "",
                "Tareas programadas:",
            ]
        )
        if self.scheduled_tasks:
            lines.extend(_render_task_lines(self.scheduled_tasks))
        else:
            lines.append("- No hay tareas persistentes abiertas.")

        lines.extend(
            [
                "",
                "Repo actual:",
                f"- proyecto: {self.context.working_set.project_name}",
                f"- git: {self.context.git.summary()}",
            ]
        )
        if self.context.git.changed_paths:
            lines.append("- ficheros cambiados:")
            lines.extend(f"  {path}" for path in self.context.git.changed_paths)
        else:
            lines.append("- ficheros cambiados: ninguno")
        return "\n".join(lines)


@dataclass(slots=True)
class DailySourceStatus:
    name: str
    ok: bool
    item_count: int = 0
    error: str | None = None


@dataclass(slots=True)
class DailyBrief:
    generated_at: datetime
    target_day: date
    context: RuntimeContext
    activity: DailyActivity
    pending_notes: list[MemoryRecord]
    scheduled_tasks: list[TaskRecord]
    local_calendar_events: list[dict[str, Any]]
    google_calendar_events: list[dict[str, Any]]
    reminders: list[dict[str, Any]]
    gmail_messages: list[dict[str, Any]]
    drive_files: list[dict[str, Any]]
    notes: list[dict[str, Any]]
    knowledge_status: KnowledgeStatus | None
    knowledge_hits: list[KnowledgeRecord]
    source_statuses: list[DailySourceStatus]

    def render(self) -> str:
        lines = [
            f"ADV ARCHON daily brief | {self.generated_at:%Y-%m-%d %H:%M}",
            "",
            "Prioridades sugeridas:",
        ]
        priorities = _derive_priorities(self)
        if priorities:
            lines.extend(f"- {item}" for item in priorities)
        else:
            lines.append("- No veo urgencias claras ahora mismo.")

        lines.extend(
            [
                "",
                "Agenda local:",
            ]
        )
        if self.local_calendar_events:
            lines.extend(_render_calendar_events(self.local_calendar_events))
        else:
            lines.append("- Sin eventos locales para este día.")

        lines.extend(
            [
                "",
                "Google Calendar:",
            ]
        )
        if self.google_calendar_events:
            lines.extend(_render_calendar_events(self.google_calendar_events))
        else:
            lines.append("- Sin eventos de Google Calendar para este día.")

        lines.extend(
            [
                "",
                "Pendientes:",
            ]
        )
        if self.scheduled_tasks:
            lines.append("- Tareas internas:")
            lines.extend(f"  {line[2:]}" for line in _render_task_lines(self.scheduled_tasks))
        else:
            lines.append("- Tareas internas: ninguna.")
        if self.reminders:
            lines.append("- Recordatorios:")
            lines.extend(f"  {line[2:]}" for line in _render_reminders(self.reminders))
        else:
            lines.append("- Recordatorios: ninguno.")

        lines.extend(
            [
                "",
                "Gmail:",
            ]
        )
        if self.gmail_messages:
            lines.extend(_render_gmail_messages(self.gmail_messages))
        else:
            lines.append("- Sin correos relevantes cargados.")

        lines.extend(
            [
                "",
                "Drive:",
            ]
        )
        if self.drive_files:
            lines.extend(_render_drive_files(self.drive_files))
        else:
            lines.append("- Sin documentos recientes o relevantes.")

        lines.extend(
            [
                "",
                "Notas y memoria:",
            ]
        )
        if self.notes:
            lines.extend(_render_notes(self.notes))
        else:
            lines.append("- Sin notas destacadas.")
        if self.pending_notes:
            lines.append("- Memoria pendiente:")
            lines.extend(f"  {line[2:]}" for line in _render_note_lines(self.pending_notes))
        else:
            lines.append("- Memoria pendiente: nada destacado.")

        lines.extend(
            [
                "",
                "Conocimiento local:",
            ]
        )
        lines.extend(_render_knowledge_section(self.knowledge_status, self.knowledge_hits))

        lines.extend(
            [
                "",
                "Contexto actual:",
                f"- perfil: {self.context.active_profile}",
                f"- proyecto: {self.context.working_set.project_name}",
                f"- git: {self.context.git.summary()}",
            ]
        )
        if self.activity.recent_events:
            lines.append("- actividad reciente:")
            lines.extend(f"  {event}" for event in self.activity.recent_events[:5])

        lines.extend(
            [
                "",
                "Estado de fuentes:",
            ]
        )
        lines.extend(_render_source_statuses(self.source_statuses))
        return "\n".join(lines)


def build_daily_brief(
    *,
    project_root: Path,
    logs_dir: Path,
    memory_store: MemoryStore,
    task_store: TaskStore | None = None,
    personal_tools: Any | None = None,
    google_tools: Any | None = None,
    knowledge_store: KnowledgeStore | None = None,
    target_day: date | None = None,
) -> DailyBrief:
    context = capture_runtime_context(project_root)
    entries = read_log_entries(logs_dir, day=target_day)
    pending_notes = memory_store.pending_notes(limit=DEFAULT_DAILY_LIMIT)
    scheduled_tasks = task_store.list_tasks(limit=DEFAULT_DAILY_LIMIT) if task_store else []
    effective_day = target_day or datetime.now().date()
    day_offset = max(0, (effective_day - datetime.now().date()).days)
    project_signal = _project_signal(context)
    notes_query = project_signal or "todo"
    drive_query = project_signal or ""
    knowledge_query = project_signal
    knowledge_roots = [str(context.working_set.project_root)] if knowledge_query else []
    source_statuses: list[DailySourceStatus] = []

    local_calendar_events = _load_payload_items(
        source_statuses,
        name="Calendario local",
        payload_key="events",
        loader=(
            None
            if personal_tools is None
            else lambda: personal_tools.calendar_upcoming(
                days=1,
                limit=8,
                start_offset_days=day_offset,
            )
        ),
    )
    reminders = _load_payload_items(
        source_statuses,
        name="Recordatorios",
        payload_key="reminders",
        loader=(None if personal_tools is None else lambda: personal_tools.reminders_list(limit=8)),
    )
    notes = _load_payload_items(
        source_statuses,
        name="Notes",
        payload_key="notes",
        loader=(
            None
            if personal_tools is None
            else lambda: personal_tools.notes_search(notes_query, limit=5)
        ),
    )
    google_calendar_events = _load_payload_items(
        source_statuses,
        name="Google Calendar",
        payload_key="events",
        loader=(
            None
            if google_tools is None
            else lambda: google_tools.gcal_list_events(
                days=1,
                max_results=8,
                start_offset_days=day_offset,
            )
        ),
    )
    gmail_messages = _load_payload_items(
        source_statuses,
        name="Gmail",
        payload_key="messages",
        loader=(
            None
            if google_tools is None
            else lambda: google_tools.gmail_search(DEFAULT_DAILY_GMAIL_QUERY, max_results=8)
        ),
    )
    drive_files = _load_payload_items(
        source_statuses,
        name="Drive",
        payload_key="files",
        loader=(
            None
            if google_tools is None
            else lambda: google_tools.drive_search(drive_query, max_results=5)
        ),
    )

    knowledge_status = _load_knowledge_status(
        source_statuses,
        knowledge_store=knowledge_store,
    )
    knowledge_hits = _load_knowledge_hits(
        source_statuses,
        knowledge_store=knowledge_store,
        query=knowledge_query,
        roots=knowledge_roots,
    )

    return DailyBrief(
        generated_at=datetime.now(),
        target_day=effective_day,
        context=context,
        activity=_summarize_activity(entries),
        pending_notes=pending_notes,
        scheduled_tasks=scheduled_tasks,
        local_calendar_events=local_calendar_events,
        google_calendar_events=google_calendar_events,
        reminders=reminders,
        gmail_messages=gmail_messages,
        drive_files=drive_files,
        notes=notes,
        knowledge_status=knowledge_status,
        knowledge_hits=knowledge_hits,
        source_statuses=source_statuses,
    )


def build_daily_report(
    *,
    project_root: Path,
    logs_dir: Path,
    memory_store: MemoryStore,
    task_store: TaskStore | None = None,
    target_day: date | None = None,
) -> DailyReport:
    context = capture_runtime_context(project_root)
    entries = read_log_entries(logs_dir, day=target_day)
    pending_notes = memory_store.pending_notes(limit=5)
    scheduled_tasks = task_store.list_tasks(limit=5) if task_store is not None else []
    return DailyReport(
        generated_at=datetime.now(),
        context=context,
        activity=_summarize_activity(entries),
        pending_notes=pending_notes,
        scheduled_tasks=scheduled_tasks,
    )


def _summarize_activity(entries: list[LogEntry]) -> DailyActivity:
    total_sessions = len([entry for entry in entries if entry.event == "session_started"])
    llm_calls = len([entry for entry in entries if entry.event == "llm_call"])
    shell_commands = len([entry for entry in entries if entry.event == "shell_exec"])
    python_execs = len([entry for entry in entries if entry.event == "python_exec"])
    memory_updates = len(
        [
            entry
            for entry in entries
            if entry.event in {"memory_remembered", "memory_forgotten"}
        ]
    )
    interesting = [
        _humanize_event(entry)
        for entry in entries[-8:]
        if entry.event not in {"user_input", "session_started"}
    ]
    return DailyActivity(
        total_sessions=total_sessions,
        llm_calls=llm_calls,
        shell_commands=shell_commands,
        python_execs=python_execs,
        memory_updates=memory_updates,
        recent_events=[item for item in interesting if item],
    )


def _humanize_event(entry: LogEntry) -> str:
    timestamp = entry.timestamp[11:16]
    if entry.event == "llm_call":
        provider = entry.fields.get("provider", "llm")
        phase = entry.fields.get("phase", "")
        tokens = entry.fields.get("total_tokens", 0)
        return f"{timestamp} | {provider} {phase} | {tokens} tok"
    if entry.event == "shell_exec":
        command = str(entry.fields.get("command", "")).strip()
        return f"{timestamp} | shell | {command}"
    if entry.event == "python_exec":
        return f"{timestamp} | python snippet"
    if entry.event == "memory_remembered":
        return f"{timestamp} | memoria guardada"
    if entry.event == "memory_forgotten":
        return f"{timestamp} | memoria borrada"
    if entry.event == "slash_web_search":
        query = str(entry.fields.get("query", "")).strip()
        return f"{timestamp} | web | {query}"
    if entry.event == "slash_read":
        path = str(entry.fields.get("path", "")).strip()
        return f"{timestamp} | lectura | {path}"
    return ""


def _project_signal(context: RuntimeContext) -> str:
    project_name = context.working_set.project_name.strip()
    if context.git.repo_root is not None or context.working_set.markers:
        return project_name
    if project_name.lower() == Path.home().name.lower():
        return ""
    return project_name


def _load_payload_items(
    source_statuses: list[DailySourceStatus],
    *,
    name: str,
    payload_key: str,
    loader: Any | None,
) -> list[dict[str, Any]]:
    if loader is None:
        source_statuses.append(
            DailySourceStatus(name=name, ok=False, error="fuente no configurada")
        )
        return []
    try:
        payload = loader().payload
        items = payload.get(payload_key, [])
        if not isinstance(items, list):
            items = []
        normalized = [item for item in items if isinstance(item, dict)]
        source_statuses.append(
            DailySourceStatus(name=name, ok=True, item_count=len(normalized))
        )
        return normalized
    except Exception as exc:
        source_statuses.append(DailySourceStatus(name=name, ok=False, error=str(exc)))
        return []


def _load_knowledge_status(
    source_statuses: list[DailySourceStatus],
    *,
    knowledge_store: KnowledgeStore | None,
) -> KnowledgeStatus | None:
    if knowledge_store is None:
        source_statuses.append(
            DailySourceStatus(name="Conocimiento local", ok=False, error="fuente no configurada")
        )
        return None
    try:
        status = knowledge_store.status()
    except Exception as exc:
        source_statuses.append(
            DailySourceStatus(name="Conocimiento local", ok=False, error=str(exc))
        )
        return None
    source_statuses.append(
        DailySourceStatus(
            name="Conocimiento local",
            ok=True,
            item_count=status.indexed_files,
        )
    )
    return status


def _load_knowledge_hits(
    source_statuses: list[DailySourceStatus],
    *,
    knowledge_store: KnowledgeStore | None,
    query: str,
    roots: list[str],
) -> list[KnowledgeRecord]:
    if knowledge_store is None or not query.strip():
        return []
    try:
        hits = knowledge_store.search(query, limit=5, roots=roots or None)
    except Exception as exc:
        source_statuses.append(
            DailySourceStatus(name="Busqueda de conocimiento", ok=False, error=str(exc))
        )
        return []
    source_statuses.append(
        DailySourceStatus(name="Busqueda de conocimiento", ok=True, item_count=len(hits))
    )
    return hits


def _derive_priorities(report: DailyBrief) -> list[str]:
    priorities: list[str] = []
    seen: set[str] = set()

    for event in [*report.local_calendar_events, *report.google_calendar_events]:
        title = str(event.get("title") or event.get("summary") or "").strip()
        if not title:
            continue
        label = f"Agenda: {title} ({_format_event_window(event)})"
        if label not in seen:
            priorities.append(label)
            seen.add(label)
        if len(priorities) >= 2:
            break

    for task in report.scheduled_tasks[:2]:
        label = f"Tarea: {task.title} ({_format_due(task.due_at)})"
        if label not in seen:
            priorities.append(label)
            seen.add(label)

    due_reminders = [
        reminder
        for reminder in report.reminders
        if _coerce_datetime(str(reminder.get("dueDate") or "")) is not None
    ]
    for reminder in due_reminders[:1]:
        title = str(reminder.get("title") or "").strip()
        due_value = str(reminder.get("dueDate") or "").strip()
        label = f"Recordatorio: {title} ({_format_due(due_value)})"
        if label not in seen:
            priorities.append(label)
            seen.add(label)

    for message in report.gmail_messages[:2]:
        subject = str(message.get("subject") or "").strip() or "(sin asunto)"
        sender = str(message.get("from") or "").strip() or "remitente desconocido"
        label = f"Correo: {subject} — {sender}"
        if label not in seen:
            priorities.append(label)
            seen.add(label)

    return priorities[:5]


def _render_calendar_events(events: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for event in events[:8]:
        title = str(event.get("title") or event.get("summary") or "(sin titulo)").strip()
        lines.append(f"- {title} | {_format_event_window(event)}")
    return lines


def _render_reminders(reminders: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for reminder in reminders[:8]:
        title = str(reminder.get("title") or "(sin titulo)").strip()
        due_value = str(reminder.get("dueDate") or "").strip()
        due_label = _format_due(due_value) if due_value else "sin fecha"
        lines.append(f"- {title} | {due_label}")
    return lines


def _render_gmail_messages(messages: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for message in messages[:8]:
        subject = str(message.get("subject") or "(sin asunto)").strip()
        sender = str(message.get("from") or "remitente desconocido").strip()
        snippet = str(message.get("snippet") or "").strip()
        if snippet:
            lines.append(f"- {subject} | {sender}\n  {snippet}")
        else:
            lines.append(f"- {subject} | {sender}")
    return lines


def _render_drive_files(files: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for drive_file in files[:5]:
        name = str(drive_file.get("name") or "(sin nombre)").strip()
        modified = str(drive_file.get("modified_time") or "").strip()
        owner = str(drive_file.get("owner") or "").strip()
        owner_label = f" | {owner}" if owner else ""
        lines.append(f"- {name} | {_format_due(modified)}{owner_label}")
    return lines


def _render_notes(notes: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for note in notes[:5]:
        title = str(note.get("title") or "(sin titulo)").strip()
        folder = str(note.get("folder") or "").strip()
        body = str(note.get("body") or "").strip()
        folder_label = f" | {folder}" if folder else ""
        lines.append(f"- {title}{folder_label}")
        if body:
            lines.append(f"  {body[:180]}")
    return lines


def _render_knowledge_section(
    status: KnowledgeStatus | None,
    hits: list[KnowledgeRecord],
) -> list[str]:
    if status is None:
        return ["- Sin acceso al indice de conocimiento local."]

    lines = [
        (
            "- indice: "
            f"{status.indexed_files} indexados | "
            f"{status.pending_files} pendientes | "
            f"{status.error_files} fallidos"
        )
    ]
    if hits:
        lines.append("- pistas relevantes:")
        for hit in hits[:5]:
            lines.append(f"  {hit.title} | {hit.path}")
    else:
        lines.append("- pistas relevantes: ninguna para el contexto actual.")
    return lines


def _render_source_statuses(source_statuses: list[DailySourceStatus]) -> list[str]:
    lines: list[str] = []
    for status in source_statuses:
        if status.ok:
            lines.append(f"- {status.name}: ok ({status.item_count})")
        else:
            lines.append(f"- {status.name}: {status.error or 'no disponible'}")
    return lines


def _format_event_window(event: dict[str, Any]) -> str:
    if bool(event.get("all_day")):
        start_value = str(event.get("start") or "").strip()
        parsed = _coerce_datetime(start_value)
        if parsed is None:
            return "todo el dia"
        return f"todo el dia ({parsed:%d/%m})"

    start_value = str(event.get("start") or "").strip()
    end_value = str(event.get("end") or "").strip()
    start_dt = _coerce_datetime(start_value)
    end_dt = _coerce_datetime(end_value)
    if start_dt is not None and end_dt is not None:
        return f"{start_dt:%H:%M}-{end_dt:%H:%M}"
    if start_dt is not None:
        return f"{start_dt:%H:%M}"
    return "sin hora"


def _format_due(value: str) -> str:
    parsed = _coerce_datetime(value)
    if parsed is None:
        return value or "sin fecha"
    return parsed.strftime("%d/%m %H:%M")


def _coerce_datetime(value: str) -> datetime | None:
    clean = value.strip()
    if not clean:
        return None
    try:
        return datetime.fromisoformat(clean)
    except ValueError:
        pass
    if len(clean) == 10:
        try:
            return datetime.fromisoformat(f"{clean}T00:00:00")
        except ValueError:
            return None
    return None


def _render_note_lines(records: list[MemoryRecord]) -> list[str]:
    lines: list[str] = []
    for record in records:
        tags = f" | tags: {', '.join(record.tags)}" if record.tags else ""
        lines.append(f"- [#{record.id}] {record.content}{tags}")
    return lines


def _render_task_lines(records: list[TaskRecord]) -> list[str]:
    lines: list[str] = []
    for record in records:
        recurrence = f" | recurrencia: {record.recurrence}" if record.recurrence else ""
        lines.append(
            f"- [#{record.id}] {record.title} | {record.status} | {record.due_at}{recurrence}"
        )
    return lines
