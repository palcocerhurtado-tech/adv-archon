from __future__ import annotations

import plistlib
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from zoneinfo import ZoneInfo

import dateparser  # type: ignore[import-untyped]

from adv_archon.core.logging import AppLogger

TERMINAL_TASK_STATUSES = {"done", "cancelled"}


@dataclass(slots=True)
class TaskRecord:
    id: int
    title: str
    prompt: str
    due_at: str
    recurrence: str | None
    status: str
    created_at: str
    updated_at: str
    last_fired_at: str | None


class TaskStore:
    def __init__(
        self,
        db_path: Path,
        *,
        timezone_name: str = "Europe/Madrid",
        notifications_enabled: bool = True,
        logger: AppLogger | None = None,
    ) -> None:
        self._db_path = db_path
        self._timezone = ZoneInfo(timezone_name)
        self._notifications_enabled = notifications_enabled
        self._logger = logger
        self._conn = self._connect()

    def create_task(
        self,
        *,
        title: str,
        due_text: str,
        prompt: str | None = None,
        recurrence: str | None = None,
    ) -> TaskRecord:
        due_at = self._parse_due_text(due_text)
        clean_title = title.strip()
        if not clean_title:
            raise ValueError("La tarea necesita un titulo.")
        task_prompt = (prompt or clean_title).strip()
        if not task_prompt:
            raise ValueError("La tarea necesita un prompt o descripcion.")
        now = datetime.now(UTC).isoformat()
        cursor = self._conn.execute(
            """
            INSERT INTO tasks (
                title, prompt, due_at, recurrence, status, created_at, updated_at, last_fired_at
            )
            VALUES (?, ?, ?, ?, 'scheduled', ?, ?, NULL)
            """,
            (
                clean_title,
                task_prompt,
                due_at,
                recurrence.strip() if recurrence else None,
                now,
                now,
            ),
        )
        self._conn.commit()
        if cursor.lastrowid is None:
            raise RuntimeError("No he podido crear la tarea.")
        record = self.get_task(int(cursor.lastrowid))
        if record is None:
            raise RuntimeError("No he podido recuperar la tarea creada.")
        if self._logger is not None:
            self._logger.log(
                "task_created",
                task_id=record.id,
                title=record.title,
                due_at=record.due_at,
                recurrence=record.recurrence,
            )
        return record

    def list_tasks(self, *, status: str | None = None, limit: int = 20) -> list[TaskRecord]:
        if status in {None, "open"}:
            rows = self._conn.execute(
                """
                SELECT id, title, prompt, due_at, recurrence, status,
                       created_at, updated_at, last_fired_at
                FROM tasks
                WHERE status NOT IN ('done', 'cancelled')
                ORDER BY due_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        elif status == "all":
            rows = self._conn.execute(
                """
                SELECT id, title, prompt, due_at, recurrence, status,
                       created_at, updated_at, last_fired_at
                FROM tasks
                ORDER BY due_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT id, title, prompt, due_at, recurrence, status,
                       created_at, updated_at, last_fired_at
                FROM tasks
                WHERE status = ?
                ORDER BY due_at ASC
                LIMIT ?
                """,
                (status, limit),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def search_tasks(self, query: str, *, limit: int = 10) -> list[TaskRecord]:
        pattern = f"%{query.lower()}%"
        rows = self._conn.execute(
            """
            SELECT id, title, prompt, due_at, recurrence, status,
                   created_at, updated_at, last_fired_at
            FROM tasks
            WHERE lower(title) LIKE ? OR lower(prompt) LIKE ?
            ORDER BY due_at ASC
            LIMIT ?
            """,
            (pattern, pattern, limit),
        ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def complete_task(self, task_id: int) -> TaskRecord | None:
        return self._set_status(task_id, status="done", event="task_completed")

    def cancel_task(self, task_id: int) -> TaskRecord | None:
        return self._set_status(task_id, status="cancelled", event="task_cancelled")

    def get_task(self, task_id: int) -> TaskRecord | None:
        row = self._conn.execute(
            """
            SELECT id, title, prompt, due_at, recurrence, status,
                   created_at, updated_at, last_fired_at
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def due_tasks(self, *, now: datetime | None = None) -> list[TaskRecord]:
        effective_now = now or datetime.now(self._timezone)
        rows = self._conn.execute(
            """
            SELECT id, title, prompt, due_at, recurrence, status,
                   created_at, updated_at, last_fired_at
            FROM tasks
            WHERE status IN ('scheduled', 'due')
            ORDER BY due_at ASC
            """
        ).fetchall()
        due: list[TaskRecord] = []
        for row in rows:
            record = self._row_to_record(row)
            due_at = datetime.fromisoformat(record.due_at).astimezone(self._timezone)
            if due_at <= effective_now:
                due.append(record)
        return due

    def run_due_tasks(self) -> list[TaskRecord]:
        now = datetime.now(self._timezone)
        records = self.due_tasks(now=now)
        fired: list[TaskRecord] = []
        for record in records:
            self._fire_notification(record)
            self._advance_task(record, fired_at=now)
            updated = self.get_task(record.id)
            if updated is not None:
                fired.append(updated)
        if self._logger is not None:
            self._logger.log("tasks_run_due", fired=len(fired))
        return fired

    def install_launch_agent(self, *, adv_command: str, interval_minutes: int = 30) -> Path:
        launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
        launch_agents_dir.mkdir(parents=True, exist_ok=True)
        plist_path = launch_agents_dir / "com.adv-archon.tasks.plist"
        plist_path.write_bytes(
            plistlib.dumps(
                {
                    "Label": "com.adv-archon.tasks",
                    "ProgramArguments": [adv_command, "tasks", "run-due"],
                    "StartInterval": interval_minutes * 60,
                    "RunAtLoad": True,
                }
            )
        )
        subprocess.run(["launchctl", "unload", str(plist_path)], check=False, capture_output=True)
        completed = subprocess.run(
            ["launchctl", "load", str(plist_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "No he podido cargar el launch agent.")
        if self._logger is not None:
            self._logger.log(
                "task_launch_agent_installed",
                plist_path=str(plist_path),
                interval_minutes=interval_minutes,
            )
        return plist_path

    def _advance_task(self, record: TaskRecord, *, fired_at: datetime) -> None:
        fired_iso = fired_at.astimezone(UTC).isoformat()
        next_due = _compute_next_due(record, fired_at)
        if next_due is None:
            status = "due"
            due_at = record.due_at
        else:
            status = "scheduled"
            due_at = next_due.astimezone(UTC).isoformat()
        self._conn.execute(
            """
            UPDATE tasks
            SET status = ?, due_at = ?, updated_at = ?, last_fired_at = ?
            WHERE id = ?
            """,
            (status, due_at, fired_iso, fired_iso, record.id),
        )
        self._conn.commit()

    def _set_status(
        self,
        task_id: int,
        *,
        status: str,
        event: str,
    ) -> TaskRecord | None:
        task = self.get_task(task_id)
        if task is None:
            return None
        now = datetime.now(UTC).isoformat()
        self._conn.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, task_id),
        )
        self._conn.commit()
        updated = self.get_task(task_id)
        if self._logger is not None and updated is not None:
            self._logger.log(event, task_id=updated.id, title=updated.title)
        return updated

    def _fire_notification(self, record: TaskRecord) -> None:
        if not self._notifications_enabled:
            return
        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification {record.prompt!r} with title "ADV ARCHON"',
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if self._logger is not None:
            self._logger.log("task_fired", task_id=record.id, title=record.title)

    def _parse_due_text(self, due_text: str) -> str:
        return parse_due_text(due_text, timezone_name=self._timezone.key).isoformat()

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                prompt TEXT NOT NULL,
                due_at TEXT NOT NULL,
                recurrence TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_fired_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tasks_due_at
            ON tasks (due_at ASC)
            """
        )
        conn.commit()
        return conn

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            id=int(row["id"]),
            title=str(row["title"]),
            prompt=str(row["prompt"]),
            due_at=str(row["due_at"]),
            recurrence=str(row["recurrence"]) if row["recurrence"] is not None else None,
            status=str(row["status"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            last_fired_at=(
                str(row["last_fired_at"]) if row["last_fired_at"] is not None else None
            ),
        )


def parse_due_text(
    due_text: str,
    *,
    timezone_name: str = "Europe/Madrid",
    relative_base: datetime | None = None,
) -> datetime:
    timezone = ZoneInfo(timezone_name)
    base = (
        relative_base.astimezone(timezone)
        if relative_base is not None
        else datetime.now(timezone)
    )
    parsed = dateparser.parse(
        due_text,
        languages=["es", "en"],
        settings={
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": base,
            "TIMEZONE": timezone.key,
            "RETURN_AS_TIMEZONE_AWARE": True,
        },
    )
    if parsed is None or not isinstance(parsed, datetime):
        raise ValueError(f"No he entendido la fecha/hora: {due_text}")
    return cast(datetime, parsed.astimezone(UTC))


def _compute_next_due(record: TaskRecord, fired_at: datetime) -> datetime | None:
    if not record.recurrence:
        return None
    recurrence = record.recurrence.lower().strip()
    due_at = datetime.fromisoformat(record.due_at).astimezone(fired_at.tzinfo)
    if recurrence in {"daily", "diario", "cada dia"}:
        return due_at.replace(
            year=fired_at.year,
            month=fired_at.month,
            day=fired_at.day,
        ) + timedelta(days=1)
    if recurrence in {"weekly", "semanal", "cada semana"}:
        return due_at + timedelta(days=7)
    if recurrence in {"weekdays", "laborables"}:
        candidate = due_at + timedelta(days=1)
        while candidate.weekday() >= 5:
            candidate += timedelta(days=1)
        return candidate
    return None
