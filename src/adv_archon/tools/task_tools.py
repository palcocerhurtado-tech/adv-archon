from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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
    ]
