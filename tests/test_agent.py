from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

from adv_archon.core.agent import Agent, ToolSpec, _TurnState
from adv_archon.core.context import GitContext, RuntimeContext, WorkingSet
from adv_archon.core.evals import KnowledgeRetrievalEval
from adv_archon.core.intent import IntentAnalysis
from adv_archon.core.knowledge import KnowledgeRecord
from adv_archon.core.llm_types import LLMResponse, LLMUsage
from adv_archon.core.session import SessionStore


class FakeLLM:
    mode = "local"

    def temporary_mode(self, _mode: str):
        from contextlib import nullcontext

        return nullcontext()

    def stream_complete(self, *_args, **_kwargs) -> LLMResponse:
        return LLMResponse(
            text="respuesta del modelo",
            usage=LLMUsage(),
            provider="fake",
            model="fake",
        )


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
                name="gcal_list_events",
                description="google calendar",
                schema={},
                fn=lambda **_kwargs: None,
            ),
            ToolSpec(
                name="gmail_search",
                description="gmail",
                schema={},
                fn=lambda **_kwargs: None,
            ),
            ToolSpec(
                name="drive_search",
                description="drive",
                schema={},
                fn=lambda **_kwargs: None,
            ),
            ToolSpec(
                name="web_library_search",
                description="web library",
                schema={},
                fn=lambda **_kwargs: None,
            ),
            ToolSpec(
                name="web_library_save_search",
                description="web library save",
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
                name="notes_create",
                description="notes create",
                schema={},
                fn=lambda **_kwargs: None,
            ),
            ToolSpec(
                name="vault_search",
                description="vault",
                schema={},
                fn=lambda **_kwargs: None,
            ),
            ToolSpec(
                name="contacts_search",
                description="contacts",
                schema={},
                fn=lambda **_kwargs: None,
            ),
            ToolSpec(
                name="reminder_create",
                description="reminders",
                schema={},
                fn=lambda **_kwargs: None,
            ),
            ToolSpec(
                name="knowledge_search",
                description="knowledge",
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
        knowledge_search_result=None,
        knowledge_eval=None,
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


def test_rule_based_plan_routes_direct_note_creation(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)

    plan = agent._rule_based_plan(
        "crea una nota titulada Ideas ADV que diga revisar Gmail y Drive",
        state,
        [],
    )

    assert plan is not None
    assert plan["tool_name"] == "notes_create"
    assert plan["arguments"] == {
        "title": "Ideas ADV",
        "body": "revisar Gmail y Drive",
    }


def test_rule_based_plan_reads_local_file_before_note_creation(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)

    plan = agent._rule_based_plan(
        "hazme una nota sobre ~/Desktop/libros/atomic-habits.pdf",
        state,
        [],
    )

    assert plan is not None
    assert plan["tool_name"] == "read_file"
    assert plan["arguments"] == {"path": "~/Desktop/libros/atomic-habits.pdf"}

    follow_up = agent._rule_based_plan(
        "hazme una nota sobre ~/Desktop/libros/atomic-habits.pdf",
        state,
        ["read_file"],
    )

    assert follow_up is None


def test_rule_based_plan_uses_knowledge_for_desktop_note_request(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)

    plan = agent._rule_based_plan(
        "hazme unos apuntes sobre el libro atomic habits del escritorio",
        state,
        [],
    )

    assert plan is not None
    assert plan["tool_name"] == "knowledge_search"
    assert plan["arguments"] == {"query": "atomic habits", "limit": 5}


def test_rule_based_plan_uses_vault_search_for_obsidian_queries(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)

    plan = agent._rule_based_plan(
        "busca en mi vault de obsidian todo lo relacionado con acme",
        state,
        [],
    )

    assert plan is not None
    assert plan["tool_name"] == "vault_search"
    assert plan["arguments"]["query"] == "obsidian acme"


def test_rule_based_plan_does_not_hijack_mail_draft_request(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)

    plan = agent._rule_based_plan(
        "redacta un email a Marta para enviarle la propuesta",
        state,
        [],
    )

    assert plan is None


def test_rule_based_plan_routes_reminder_creation_request(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)

    plan = agent._rule_based_plan(
        "crea un recordatorio para mañana a las 9 de llamar a Acme",
        state,
        [],
    )

    assert plan is not None
    assert plan["tool_name"] == "reminder_create"
    assert plan["arguments"] == {
        "title": "llamar a acme",
        "due_text": "mañana a las 9",
    }


def test_rule_based_plan_routes_alarm_request(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)

    plan = agent._rule_based_plan(
        "ponme una alarma a las 16:33",
        state,
        [],
    )

    assert plan is not None
    assert plan["tool_name"] == "reminder_create"
    assert plan["arguments"] == {
        "title": "Alarma",
        "due_text": "hoy a las 16:33",
    }


def test_rule_based_plan_routes_google_calendar_lookup(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)

    plan = agent._rule_based_plan(
        "que tengo mañana en google calendar",
        state,
        [],
    )

    assert plan is not None
    assert plan["tool_name"] == "gcal_list_events"
    assert plan["arguments"] == {
        "days": 1,
        "max_results": 20,
        "start_offset_days": 1,
    }


def test_rule_based_plan_routes_gmail_search(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)

    plan = agent._rule_based_plan(
        "busca en gmail todo lo relacionado con acme",
        state,
        [],
    )

    assert plan is not None
    assert plan["tool_name"] == "gmail_search"
    assert plan["arguments"] == {
        "query": "acme",
        "max_results": 10,
    }


def test_rule_based_plan_routes_drive_search(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)

    plan = agent._rule_based_plan(
        "busca en google drive la propuesta acme",
        state,
        [],
    )

    assert plan is not None
    assert plan["tool_name"] == "drive_search"
    assert plan["arguments"] == {
        "query": "propuesta acme",
        "max_results": 10,
    }


def test_rule_based_plan_routes_web_library_search(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)

    plan = agent._rule_based_plan(
        "busca en tu biblioteca web todo lo relacionado con consultoria ia",
        state,
        [],
    )

    assert plan is not None
    assert plan["tool_name"] == "web_library_search"
    assert plan["arguments"] == {
        "query": "consultoria",
        "limit": 8,
    }


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


def test_rule_based_plan_for_next_week_uses_next_monday_window(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)

    plan = agent._rule_based_plan(
        "mira a ver que tengo en mi calendario la semana que entra",
        state,
        [],
    )

    assert plan is not None
    assert plan["tool_name"] == "calendar_upcoming"
    assert plan["arguments"] == {"days": 7, "limit": 20, "start_offset_days": 6}


def test_deterministic_calendar_tool_error_does_not_ask_for_retry(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)

    response = agent._deterministic_tool_error_response(
        user_input="mira a ver que tengo en mi calendario la semana que entra",
        tool_name="calendar_upcoming",
        payload={"error": "El conector personal ha tardado demasiado y se ha cancelado."},
    )

    assert response is not None
    assert "la semana que viene" in response.text
    assert "¿Quieres" not in response.text
    assert "vuelve a probar" in response.text


def test_force_local_private_context_for_documents_query(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = replace(
        _build_state(tmp_path),
        intent=IntentAnalysis(
            category="documents",
            profile="general",
            needs_plan=False,
            needs_knowledge=True,
            needs_web=False,
            needs_shell=False,
            reasons=["documentos"],
        ),
    )

    assert agent._should_force_local_for_turn(
        "resume ~/Desktop/propuesta.pdf",
        state,
    ) is True


def test_force_local_private_context_not_triggered_for_public_web_query(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = replace(
        _build_state(tmp_path),
        intent=IntentAnalysis(
            category="web",
            profile="general",
            needs_plan=False,
            needs_knowledge=False,
            needs_web=True,
            needs_shell=False,
            reasons=["web"],
        ),
    )

    assert agent._should_force_local_for_turn(
        "busca tendencias de mercado de IA en europa",
        state,
    ) is False


def test_build_context_snapshot_uses_sober_checkpoint_and_confidence(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = replace(
        _build_state(tmp_path),
        knowledge_hits=[
            KnowledgeRecord(
                path="/tmp/atomic-habits.md",
                title="atomic-habits.md",
                excerpt="Ideas clave del libro",
                root="/tmp",
                content_type="md",
                updated_at="2026-04-24T08:00:00+00:00",
                score=0.93,
                term_coverage=0.8,
            )
        ],
        knowledge_eval=KnowledgeRetrievalEval(
            confidence="high",
            result_count=1,
            candidate_count=8,
            top_score=0.93,
            max_term_coverage=0.8,
            avg_term_coverage=0.8,
            rationale=("resultado local fuerte",),
        ),
    )

    packet = agent._build_context_packet(
        user_input="hazme unos apuntes sobre atomic habits",
        state=state,
        plan={"kind": "tool", "step_summary": "buscar en conocimiento local para resumir luego"},
        tool_observations=[],
    )
    snapshot = agent._build_context_snapshot(packet)

    assert snapshot.checkpoint == "buscar en conocimiento local para"
    assert snapshot.confidence_hint == "conocimiento local fuerte"
    assert snapshot.knowledge_hits


def test_build_confidence_block_cites_local_evidence(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = replace(
        _build_state(tmp_path),
        knowledge_hits=[
            KnowledgeRecord(
                path="/tmp/roadmap-acme.md",
                title="roadmap-acme.md",
                excerpt="Roadmap ACME",
                root="/tmp",
                content_type="md",
                updated_at="2026-04-24T08:00:00+00:00",
                score=0.88,
                matched_terms=("roadmap", "acme"),
                term_coverage=1.0,
            )
        ],
        knowledge_eval=KnowledgeRetrievalEval(
            confidence="high",
            result_count=1,
            candidate_count=10,
            top_score=0.88,
            max_term_coverage=1.0,
            avg_term_coverage=1.0,
            rationale=("recuperacion local fuerte",),
        ),
    )

    block = agent._build_confidence_block(state=state, tool_observations=[])

    assert "Base y confianza:" in block
    assert "roadmap-acme.md" in block
    assert "confianza: media" in block or "confianza: alta" in block
