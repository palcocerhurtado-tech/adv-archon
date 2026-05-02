from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from adv_archon.core.executive_automation import (
    build_executive_automation_bundle,
    install_executive_automation,
    list_executive_automation_presets,
)
from adv_archon.core.tasks import TaskStore

ConfirmCallback = Callable[[str], bool]


@dataclass(slots=True)
class ToolResult:
    name: str
    payload: dict[str, Any]


class TaskTools:
    def __init__(
        self,
        store: TaskStore,
        *,
        confirm: ConfirmCallback,
        allow_mutations: bool = True,
    ) -> None:
        self._store = store
        self._confirm = confirm
        self._allow_mutations = allow_mutations

    def task_create(
        self,
        title: str,
        due_text: str,
        prompt: str | None = None,
        recurrence: str | None = None,
    ) -> ToolResult:
        self._ensure_mutations_allowed()
        question = (
            "Se va a crear una tarea persistente.\n"
            f"Titulo: {title}\n"
            f"Cuando: {due_text}\n"
            f"Recurrencia: {recurrence or 'ninguna'}\n"
            "¿Confirmas?"
        )
        if not self._confirm(question):
            raise PermissionError("Creacion de tarea cancelada por el usuario.")
        record = self._store.create_task(
            title=title,
            due_text=due_text,
            prompt=prompt,
            recurrence=recurrence,
        )
        return ToolResult(
            name="task_create",
            payload={
                "id": record.id,
                "title": record.title,
                "prompt": record.prompt,
                "due_at": record.due_at,
                "recurrence": record.recurrence,
                "status": record.status,
            },
        )

    def task_list(self, status: str | None = None, limit: int = 20) -> ToolResult:
        records = self._store.list_tasks(status=status, limit=limit)
        return ToolResult(
            name="task_list",
            payload={
                "tasks": [
                    {
                        "id": record.id,
                        "title": record.title,
                        "prompt": record.prompt,
                        "due_at": record.due_at,
                        "recurrence": record.recurrence,
                        "status": record.status,
                        "category": record.category,
                        "source": record.source,
                        "metadata": record.metadata,
                    }
                    for record in records
                ]
            },
        )

    def task_search(self, query: str, limit: int = 10) -> ToolResult:
        records = self._store.search_tasks(query, limit=limit)
        return ToolResult(
            name="task_search",
            payload={
                "query": query,
                "tasks": [
                    {
                        "id": record.id,
                        "title": record.title,
                        "prompt": record.prompt,
                        "due_at": record.due_at,
                        "recurrence": record.recurrence,
                        "status": record.status,
                        "category": record.category,
                        "source": record.source,
                        "metadata": record.metadata,
                    }
                    for record in records
                ],
            },
        )

    def task_complete(self, task_id: int) -> ToolResult:
        self._ensure_mutations_allowed()
        question = f"Se va a marcar la tarea #{task_id} como completada. ¿Confirmas?"
        if not self._confirm(question):
            raise PermissionError("Completado de tarea cancelado por el usuario.")
        record = self._store.complete_task(task_id)
        if record is None:
            raise ValueError(f"No encuentro la tarea #{task_id}.")
        return ToolResult(
            name="task_complete",
            payload={
                "id": record.id,
                "title": record.title,
                "status": record.status,
            },
        )

    def task_cancel(self, task_id: int) -> ToolResult:
        self._ensure_mutations_allowed()
        question = f"Se va a cancelar la tarea #{task_id}. ¿Confirmas?"
        if not self._confirm(question):
            raise PermissionError("Cancelacion de tarea cancelada por el usuario.")
        record = self._store.cancel_task(task_id)
        if record is None:
            raise ValueError(f"No encuentro la tarea #{task_id}.")
        return ToolResult(
            name="task_cancel",
            payload={
                "id": record.id,
                "title": record.title,
                "status": record.status,
            },
        )

    def task_install_agent(self, interval_minutes: int = 30) -> ToolResult:
        self._ensure_mutations_allowed()
        adv_command = shutil.which("adv-archon") or shutil.which("adv")
        if adv_command is None:
            raise RuntimeError("No encuentro `adv-archon` en PATH.")
        question = (
            "Se va a instalar un scheduler persistente con launchd para ejecutar tareas.\n"
            f"Intervalo: cada {interval_minutes} minutos\n"
            "¿Confirmas?"
        )
        if not self._confirm(question):
            raise PermissionError("Instalacion del scheduler cancelada por el usuario.")
        plist_path = self._store.install_launch_agent(
            adv_command=adv_command,
            interval_minutes=interval_minutes,
        )
        return ToolResult(
            name="task_install_agent",
            payload={
                "plist_path": str(plist_path),
                "interval_minutes": interval_minutes,
            },
        )

    def task_list_automation_presets(self) -> ToolResult:
        return ToolResult(
            name="task_list_automation_presets",
            payload={"presets": list_executive_automation_presets()},
        )

    def task_install_executive_automation(
        self,
        study_focus: str = "tu linea actual de estudio",
        morning_time: str = "08:00",
        triage_times: list[str] | None = None,
        study_time: str = "19:30",
        nightly_review_time: str = "21:30",
        meeting_prep_window_minutes: int = 45,
        meeting_prep_poll_minutes: int = 15,
    ) -> ToolResult:
        self._ensure_mutations_allowed()
        adv_command = shutil.which("adv-archon") or shutil.which("adv")
        if adv_command is None:
            raise RuntimeError("No encuentro `adv-archon` en PATH.")
        triage_schedule = tuple(triage_times or ["09:00", "14:00", "18:00"])
        question = (
            "Se va a instalar la automatizacion ejecutiva local.\n"
            f"Briefing de manana: {morning_time}\n"
            f"Triage de Gmail: {', '.join(triage_schedule)}\n"
            f"Bloque de estudio: {study_time} | foco: {study_focus}\n"
            f"Revision nocturna: {nightly_review_time}\n"
            f"Prep de reuniones: ventana {meeting_prep_window_minutes} min, sondeo cada "
            f"{meeting_prep_poll_minutes} min\n"
            "¿Confirmas?"
        )
        if not self._confirm(question):
            raise PermissionError(
                "Instalacion de automatizacion ejecutiva cancelada por el usuario."
            )
        bundle = build_executive_automation_bundle(
            morning_time=morning_time,
            triage_times=triage_schedule,
            study_time=study_time,
            nightly_review_time=nightly_review_time,
            study_focus=study_focus,
            meeting_prep_window_minutes=meeting_prep_window_minutes,
            meeting_prep_poll_minutes=meeting_prep_poll_minutes,
        )
        installed = install_executive_automation(
            store=self._store,
            adv_command=adv_command,
            bundle=bundle,
        )
        return ToolResult(
            name="task_install_executive_automation",
            payload={
                "bundle": installed.bundle.key,
                "launch_agents": [
                    {
                        "label": record.label,
                        "plist_path": str(record.plist_path),
                        "start_interval": record.start_interval,
                        "start_calendar_interval": list(record.start_calendar_interval),
                    }
                    for record in installed.launch_agents
                ],
                "tasks": [
                    {
                        "id": record.id,
                        "title": record.title,
                        "due_at": record.due_at,
                        "recurrence": record.recurrence,
                        "category": record.category,
                        "source": record.source,
                        "metadata": record.metadata,
                    }
                    for record in installed.tasks
                ],
            },
        )

    def _ensure_mutations_allowed(self) -> None:
        if not self._allow_mutations:
            raise PermissionError("En modo incógnito no se pueden crear o modificar tareas.")


def build_task_tool_specs(tool: TaskTools) -> list[dict[str, Any]]:
    return [
        {
            "name": "task_create",
            "description": "Create a persistent reminder or scheduled task after confirmation.",
            "schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "due_text": {"type": "string"},
                    "prompt": {"type": "string"},
                    "recurrence": {"type": "string"},
                },
                "required": ["title", "due_text"],
            },
            "fn": tool.task_create,
        },
        {
            "name": "task_list",
            "description": "List the user's scheduled or open persistent tasks.",
            "schema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": [],
            },
            "fn": tool.task_list,
        },
        {
            "name": "task_search",
            "description": "Search the user's persistent tasks by title or prompt.",
            "schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
            },
            "fn": tool.task_search,
        },
        {
            "name": "task_list_automation_presets",
            "description": "List reusable local automation presets for executive workflows.",
            "schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
            "fn": tool.task_list_automation_presets,
        },
        {
            "name": "task_complete",
            "description": "Mark a persistent task as done after confirmation.",
            "schema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                },
                "required": ["task_id"],
            },
            "fn": tool.task_complete,
        },
        {
            "name": "task_cancel",
            "description": "Cancel a persistent task after confirmation.",
            "schema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                },
                "required": ["task_id"],
            },
            "fn": tool.task_cancel,
        },
        {
            "name": "task_install_agent",
            "description": (
                "Install the background launchd scheduler for due tasks "
                "after confirmation."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "interval_minutes": {"type": "integer"},
                },
                "required": [],
            },
            "fn": tool.task_install_agent,
        },
        {
            "name": "task_install_executive_automation",
            "description": (
                "Install reusable launchd + persistent executive automations for morning brief, "
                "meeting prep, Gmail triage, study review, and nightly review."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "study_focus": {"type": "string"},
                    "morning_time": {"type": "string"},
                    "triage_times": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "study_time": {"type": "string"},
                    "nightly_review_time": {"type": "string"},
                    "meeting_prep_window_minutes": {"type": "integer"},
                    "meeting_prep_poll_minutes": {"type": "integer"},
                },
                "required": [],
            },
            "fn": tool.task_install_executive_automation,
        },
    ]
