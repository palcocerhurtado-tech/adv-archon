from __future__ import annotations

from datetime import datetime
from pathlib import Path

from adv_archon.core.agent import Agent, ToolSpec, _TurnState
from adv_archon.core.context import GitContext, RuntimeContext, WorkingSet
from adv_archon.core.intent import IntentAnalysis
from adv_archon.core.session import SessionStore


class FakeLLM:
    pass


def _build_agent(tmp_path: Path) -> Agent:
    return Agent(
        llm=FakeLLM(),  # type: ignore[arg-type]
        system_prompt="system",
        session=SessionStore(tmp_path),
        project_root=tmp_path,
        extra_tools=[
            ToolSpec(
                name="calendar_upcoming",
                description="calendar",
                schema={},
                fn=lambda **_kwargs: None,
            ),
            ToolSpec(
                name="task_list",
                description="tasks",
                schema={},
                fn=lambda **_kwargs: None,
            ),
            ToolSpec(
                name="notes_search",
                description="notes",
                schema={},
                fn=lambda **_kwargs: None,
            ),
            ToolSpec(
                name="contacts_search",
                description="contacts",
                schema={},
                fn=lambda **_kwargs: None,
            ),
        ],
    )


def _build_state(tmp_path: Path) -> _TurnState:
    return _TurnState(
        runtime_context=RuntimeContext(
            cwd=tmp_path,
            now=datetime(2026, 4, 21, 9, 10),
            git=GitContext(
                repo_root=None,
                branch=None,
                dirty=False,
                changed_files=0,
                changed_paths=[],
            ),
            working_set=WorkingSet(
                project_root=tmp_path,
                project_name="home",
                markers=[],
                top_entries=[],
            ),
        ),
        intent=IntentAnalysis(
            category="assistant",
            profile="general",
            needs_plan=True,
            needs_knowledge=False,
            needs_web=False,
            needs_shell=False,
            reasons=["keywords de asistente personal"],
        ),
        memories=[],
        knowledge_hits=[],
    )


def test_rule_based_plan_prioritizes_calendar_then_tasks(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)

    first_plan = agent._rule_based_plan(
        "que tengo esta semana en el calendario y qué tareas pendientes tengo",
        state,
        [],
    )
    second_plan = agent._rule_based_plan(
        "que tengo esta semana en el calendario y qué tareas pendientes tengo",
        state,
        ["calendar_upcoming"],
    )

    assert first_plan is not None
    assert first_plan["tool_name"] == "calendar_upcoming"
    assert first_plan["arguments"] == {"days": 6, "limit": 20, "start_offset_days": 0}
    assert second_plan is not None
    assert second_plan["tool_name"] == "task_list"
    assert second_plan["arguments"] == {"status": "open", "limit": 20}


def test_rule_based_plan_uses_notes_connector_for_note_queries(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)

    plan = agent._rule_based_plan(
        "busca en mis notas todo lo relacionado con propuesta acme",
        state,
        [],
    )

    assert plan is not None
    assert plan["tool_name"] == "notes_search"
    assert plan["arguments"]["query"] == "propuesta acme"


def test_rule_based_plan_does_not_hijack_mail_draft_request(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)

    plan = agent._rule_based_plan(
        "redacta un email a Marta para enviarle la propuesta",
        state,
        [],
    )

    assert plan is None


def test_rule_based_plan_does_not_hijack_reminder_creation_request(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)

    plan = agent._rule_based_plan(
        "crea un recordatorio para mañana a las 9 de llamar a Acme",
        state,
        [],
    )

    assert plan is None


def test_rule_based_plan_for_tomorrow_uses_offset_window(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)

    plan = agent._rule_based_plan(
        "que tengo mañana en el calendario",
        state,
        [],
    )

    assert plan is not None
    assert plan["tool_name"] == "calendar_upcoming"
    assert plan["arguments"] == {"days": 1, "limit": 20, "start_offset_days": 1}
