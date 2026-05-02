from datetime import date
from pathlib import Path

import numpy as np

from adv_archon.core.daily import build_daily_brief, build_daily_report
from adv_archon.core.knowledge import KnowledgeStore
from adv_archon.core.logging import AppLogger
from adv_archon.core.memory import MemoryStore
from adv_archon.core.tasks import TaskStore


class FakeEncoder:
    def encode_texts(self, texts: list[str]) -> np.ndarray:
        rows = []
        for text in texts:
            lowered = text.lower()
            vector = np.array(
                [
                    1.0 if "todo" in lowered else 0.0,
                    1.0 if "note" in lowered or "nota" in lowered else 0.0,
                    float(len(lowered) % 5 + 1),
                ],
                dtype=np.float32,
            )
            norm = np.linalg.norm(vector)
            rows.append(vector if norm == 0 else vector / norm)
        return np.vstack(rows)


class FakeToolResult:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload


class FakePersonalTools:
    def calendar_upcoming(
        self,
        days: int = 7,
        limit: int = 20,
        start_offset_days: int = 0,
    ) -> FakeToolResult:
        return FakeToolResult(
            {
                "events": [
                    {
                        "title": "Reunion ACME",
                        "start": "2026-04-22T10:00:00",
                        "end": "2026-04-22T11:00:00",
                        "all_day": False,
                    }
                ]
            }
        )

    def reminders_list(self, limit: int = 20) -> FakeToolResult:
        return FakeToolResult(
            {
                "reminders": [
                    {
                        "title": "Llamar a Marta",
                        "dueDate": "2026-04-22T12:00:00",
                    }
                ]
            }
        )

    def notes_search(self, query: str, limit: int = 10) -> FakeToolResult:
        return FakeToolResult(
            {
                "notes": [
                    {
                        "folder": "Trabajo",
                        "title": "Plan ACME",
                        "body": f"Nota para {query}",
                    }
                ]
            }
        )


class FakeGoogleTools:
    def gcal_list_events(
        self,
        days: int = 7,
        max_results: int = 20,
        start_offset_days: int = 0,
    ) -> FakeToolResult:
        return FakeToolResult(
            {
                "events": [
                    {
                        "summary": "Demo cliente",
                        "start": "2026-04-22T16:00:00",
                        "end": "2026-04-22T16:30:00",
                        "all_day": False,
                    }
                ]
            }
        )

    def gmail_search(self, query: str = "", max_results: int | None = None) -> FakeToolResult:
        return FakeToolResult(
            {
                "messages": [
                    {
                        "subject": "Propuesta ACME",
                        "from": "cliente@example.com",
                        "snippet": "Necesito respuesta hoy.",
                    }
                ]
            }
        )

    def drive_search(self, query: str = "", max_results: int | None = None) -> FakeToolResult:
        return FakeToolResult(
            {
                "files": [
                    {
                        "name": "Propuesta ACME v3",
                        "modified_time": "2026-04-22T08:30:00",
                        "owner": "Pablo",
                    }
                ]
            }
        )


def test_build_daily_report_summarizes_logs_and_pending_notes(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "pyproject.toml").write_text(
        "[project]\nname = 'daily-demo'\n",
        encoding="utf-8",
    )

    logs_dir = tmp_path / "logs"
    logger = AppLogger(logs_dir, session_id="session-1", persist=True)
    logger.log("session_started", cwd=str(project_root))
    logger.log(
        "llm_call",
        provider="gemini",
        phase="assistant",
        total_tokens=42,
        estimated_cost_usd=0.0001,
    )
    logger.log("shell_exec", command="git status")

    memory_store = MemoryStore(
        tmp_path / "memory.db",
        encoder=FakeEncoder(),
    )
    memory_store.remember("TODO: revisar propuesta ACME", ["todo", "note"])
    task_store = TaskStore(
        tmp_path / "tasks.db",
        timezone_name="Europe/Madrid",
        notifications_enabled=False,
        logger=logger,
    )
    task_store.create_task(title="Llamar a ACME", due_text="2026-04-22 09:00")

    report = build_daily_report(
        project_root=project_root,
        logs_dir=logs_dir,
        memory_store=memory_store,
        task_store=task_store,
        target_day=date.today(),
    )

    rendered = report.render()

    assert "daily-demo" in rendered
    assert "llamadas LLM: 1" in rendered
    assert "comandos shell: 1" in rendered
    assert "TODO: revisar propuesta ACME" in rendered
    assert "Llamar a ACME" in rendered


def test_build_daily_brief_collects_multisource_context(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "pyproject.toml").write_text(
        "[project]\nname = 'acme-ops'\n",
        encoding="utf-8",
    )
    docs = project_root / "docs"
    docs.mkdir()
    (docs / "roadmap-acme.md").write_text(
        "Roadmap ACME con prioridades y demo cliente",
        encoding="utf-8",
    )

    logs_dir = tmp_path / "logs"
    logger = AppLogger(logs_dir, session_id="session-brief", persist=True)
    logger.log("session_started", cwd=str(project_root))
    logger.log("llm_call", provider="ollama", phase="assistant", total_tokens=128)

    memory_store = MemoryStore(
        tmp_path / "memory.db",
        encoder=FakeEncoder(),
    )
    memory_store.remember("TODO: cerrar propuesta ACME", ["todo"])
    task_store = TaskStore(
        tmp_path / "tasks.db",
        timezone_name="Europe/Madrid",
        notifications_enabled=False,
        logger=logger,
    )
    task_store.create_task(title="Enviar propuesta ACME", due_text="2026-04-22 09:00")
    knowledge_store = KnowledgeStore(
        tmp_path / "knowledge.db",
        encoder=FakeEncoder(),
        default_roots=[str(project_root)],
        auto_index_on_search=False,
        max_files_per_root=20,
    )
    knowledge_store.run_once([project_root])

    report = build_daily_brief(
        project_root=project_root,
        logs_dir=logs_dir,
        memory_store=memory_store,
        task_store=task_store,
        personal_tools=FakePersonalTools(),
        google_tools=FakeGoogleTools(),
        knowledge_store=knowledge_store,
        target_day=date.today(),
    )

    rendered = report.render()

    assert "ADV ARCHON daily brief" in rendered
    assert "Reunion ACME" in rendered
    assert "Demo cliente" in rendered
    assert "Propuesta ACME" in rendered
    assert "Propuesta ACME v3" in rendered
    assert "Plan ACME" in rendered
    assert "roadmap-acme.md" in rendered
    assert "Estado de fuentes" in rendered
