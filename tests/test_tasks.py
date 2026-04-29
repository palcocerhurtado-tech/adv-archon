from __future__ import annotations

import plistlib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from adv_archon.core.tasks import LaunchAgentRecord, TaskRecord, TaskStore, _compute_next_due


def test_task_store_create_search_and_status_transitions(tmp_path: Path) -> None:
    store = TaskStore(
        tmp_path / "tasks.db",
        timezone_name="Europe/Madrid",
        notifications_enabled=False,
    )

    created = store.create_task(
        title="Revisar propuesta ACME",
        due_text="2026-04-22 09:30",
        recurrence="weekly",
    )
    cancelled_task = store.create_task(
        title="Cancelar demo",
        due_text="2026-04-23 12:00",
    )

    listed = store.list_tasks()
    searched = store.search_tasks("ACME")
    completed = store.complete_task(created.id)
    cancelled = store.cancel_task(cancelled_task.id)

    assert [record.title for record in listed] == [
        "Revisar propuesta ACME",
        "Cancelar demo",
    ]
    assert searched[0].id == created.id
    assert completed is not None
    assert completed.status == "done"
    assert cancelled is not None
    assert cancelled.status == "cancelled"
    assert store.list_tasks() == []


def test_task_store_due_tasks_respects_requested_time(tmp_path: Path) -> None:
    store = TaskStore(
        tmp_path / "tasks.db",
        timezone_name="Europe/Madrid",
        notifications_enabled=False,
    )
    record = store.create_task(
        title="Enviar propuesta",
        due_text="2026-04-21 09:00",
    )

    due = store.due_tasks(
        now=datetime(2026, 4, 21, 10, 0, tzinfo=ZoneInfo("Europe/Madrid"))
    )

    assert [item.id for item in due] == [record.id]


def test_task_store_upsert_persists_automation_metadata(tmp_path: Path) -> None:
    store = TaskStore(
        tmp_path / "tasks.db",
        timezone_name="Europe/Madrid",
        notifications_enabled=False,
    )

    created = store.upsert_task(
        title="Bloque de estudio",
        due_text="2026-04-21 19:30",
        prompt="Repasar grimorios",
        recurrence="daily",
        category="study",
        source="automation:study",
        metadata={"focus": "grimorios"},
    )
    updated = store.upsert_task(
        title="Bloque de estudio",
        due_text="2026-04-22 19:30",
        prompt="Repasar simbolismo",
        recurrence="daily",
        category="study",
        source="automation:study",
        metadata={"focus": "simbolismo"},
    )

    listed = store.list_tasks(source="automation:study")

    assert created.id == updated.id
    assert len(listed) == 1
    assert listed[0].category == "study"
    assert listed[0].source == "automation:study"
    assert listed[0].metadata == {"focus": "simbolismo"}
    assert listed[0].prompt == "Repasar simbolismo"


def test_install_named_launch_agent_supports_calendar_schedule(tmp_path: Path) -> None:
    store = TaskStore(
        tmp_path / "tasks.db",
        timezone_name="Europe/Madrid",
        notifications_enabled=False,
    )

    record = store.install_named_launch_agent(
        label="com.adv-archon.test-automation",
        program_arguments=["/usr/bin/env", "echo", "hola"],
        start_calendar_interval=[{"Hour": 8, "Minute": 0}, {"Hour": 18, "Minute": 0}],
        launch_agents_dir=tmp_path / "LaunchAgents",
        stdout_path=tmp_path / "logs" / "automation.out.log",
        stderr_path=tmp_path / "logs" / "automation.err.log",
        load=False,
    )

    plist_payload = plistlib.loads(record.plist_path.read_bytes())

    assert isinstance(record, LaunchAgentRecord)
    assert record.start_interval is None
    assert plist_payload["Label"] == "com.adv-archon.test-automation"
    assert plist_payload["ProgramArguments"] == ["/usr/bin/env", "echo", "hola"]
    assert plist_payload["StartCalendarInterval"] == [
        {"Hour": 8, "Minute": 0},
        {"Hour": 18, "Minute": 0},
    ]
    assert plist_payload["StandardOutPath"].endswith("automation.out.log")
    assert plist_payload["StandardErrorPath"].endswith("automation.err.log")


def test_compute_next_due_supports_daily_and_weekdays() -> None:
    fired_at = datetime(2026, 4, 24, 9, 0, tzinfo=ZoneInfo("Europe/Madrid"))
    record = TaskRecord(
        id=1,
        title="Daily standup",
        prompt="Daily standup",
        due_at="2026-04-24T09:00:00+02:00",
        recurrence="daily",
        status="scheduled",
        created_at="2026-04-20T09:00:00+02:00",
        updated_at="2026-04-20T09:00:00+02:00",
        last_fired_at=None,
    )
    weekday_record = TaskRecord(
        id=2,
        title="Laborables",
        prompt="Laborables",
        due_at="2026-04-24T09:00:00+02:00",
        recurrence="laborables",
        status="scheduled",
        created_at="2026-04-20T09:00:00+02:00",
        updated_at="2026-04-20T09:00:00+02:00",
        last_fired_at=None,
    )

    next_daily = _compute_next_due(record, fired_at)
    next_weekday = _compute_next_due(weekday_record, fired_at)

    assert next_daily is not None
    assert next_daily.day == 25
    assert next_weekday is not None
    assert next_weekday.day == 27
    assert next_weekday.weekday() == 0
