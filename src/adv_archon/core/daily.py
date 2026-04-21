from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from adv_archon.core.context import RuntimeContext, capture_runtime_context
from adv_archon.core.logging import LogEntry, read_log_entries
from adv_archon.core.memory import MemoryRecord, MemoryStore
from adv_archon.core.tasks import TaskRecord, TaskStore


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
            f"ADV ARCHON daily | {self.generated_at:%Y-%m-%d %H:%M}",
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
        if entry.event
        not in {"user_input", "session_started"}
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
