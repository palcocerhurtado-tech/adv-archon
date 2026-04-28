from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from adv_archon.core.agent import Agent, ToolSpec, _TurnState
from adv_archon.core.context import GitContext, RuntimeContext, WorkingSet
from adv_archon.core.context_packets import ToolObservation
from adv_archon.core.evals import KnowledgeRetrievalEval, summarize_response_confidence
from adv_archon.core.intent import IntentAnalysis
from adv_archon.core.knowledge import KnowledgeRecord
from adv_archon.core.llm_types import LLMResponse, LLMUsage
from adv_archon.core.session import SessionMessage, SessionStore


class FakeLLM:
    mode = "local"
    tool_call_repair_enabled = True

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


class RecordingLLM(FakeLLM):
    def __init__(self) -> None:
        self.messages = None
        self.system_prompt = None

    def stream_complete(self, messages, **kwargs) -> LLMResponse:
        self.messages = list(messages)
        self.system_prompt = kwargs.get("system_prompt")
        on_chunk = kwargs.get("on_chunk")
        text = "resumen listo"
        if on_chunk is not None:
            on_chunk(text)
        return LLMResponse(
            text=text,
            usage=LLMUsage(),
            provider="fake",
            model="fake",
        )


class ExplodingMemoryStore:
    def count(self) -> int:
        return 1

    def context_matches(self, *_args, **_kwargs):
        raise AssertionError("No debería consultar memoria para un adjunto directo.")


class ExplodingKnowledgeStore:
    def search_details(self, *_args, **_kwargs):
        raise AssertionError("No debería consultar conocimiento para un adjunto directo.")


class FakeMemoryStore:
    def __init__(self, records=None, count: int | None = None) -> None:
        self._records = list(records or [])
        self._count = len(self._records) if count is None else count
        self.saved_records: list[object] = []

    def count(self) -> int:
        return self._count

    def context_matches(self, *_args, **_kwargs):
        return list(self._records)

    def find_matches(self, query_or_id: str, *, limit: int = 5):
        query = str(query_or_id).lower()
        matches = [
            record
            for record in self._records
            if query in getattr(record, "content", "").lower()
            or any(query in str(tag).lower() for tag in getattr(record, "tags", []))
        ]
        return matches[:limit]

    def remember(
        self,
        content: str,
        tags=None,
        *,
        source: str = "agent",
        memory_type: str = "fact",
        namespace: str = "general",
        metadata=None,
    ):
        record = type(
            "Record",
            (),
            {
                "id": len(self.saved_records) + 1,
                "content": content,
                "tags": list(tags or []),
                "source": source,
                "memory_type": memory_type,
                "namespace": namespace,
                "metadata": metadata or {},
            },
        )()
        self.saved_records.append(record)
        self._records.append(record)
        self._count += 1
        return record


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
                schema={
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer"},
                        "max_results": {"type": "integer"},
                        "start_offset_days": {"type": "integer"},
                    },
                },
                fn=lambda **_kwargs: None,
            ),
            ToolSpec(
                name="gmail_search",
                description="gmail",
                schema={},
                fn=lambda **_kwargs: None,
            ),
            ToolSpec(
                name="gmail_read_thread",
                description="gmail read thread",
                schema={},
                fn=lambda **_kwargs: None,
            ),
            ToolSpec(
                name="gmail_draft",
                description="gmail draft",
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
            ToolSpec(
                name="shell_exec",
                description="shell",
                schema={},
                fn=lambda **_kwargs: None,
            ),
            ToolSpec(
                name="browser_open",
                description="browser",
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


def test_rule_based_plan_creates_note_from_recent_document_context(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)
    agent._session.append(
        SessionMessage(
            role="tool",
            name="read_file",
            content=json.dumps(
                {
                    "path": "/Users/pabloalcocer/Desktop/LA GRASA/La Clavicula de Salomon.pdf",
                    "content": "contenido del libro",
                },
                ensure_ascii=False,
            ),
        )
    )
    agent._session.append(
        SessionMessage(
            role="assistant",
            content="Resumen\n\n- idea uno\n- idea dos",
        )
    )

    plan = agent._rule_based_plan(
        "crea una nota con el resumen de este libro",
        state,
        [],
    )

    assert plan is not None
    assert plan["tool_name"] == "notes_create"
    assert plan["arguments"]["title"] == "Resumen de La Clavicula de Salomon"
    assert "idea uno" in plan["arguments"]["body"]


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


def test_rule_based_plan_reads_attached_pdf_before_planning_more(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)

    plan = agent._rule_based_plan(
        "resume este PDF\n\nAdjuntos disponibles:\n- /tmp/demo.pdf\n\nÁbrelos si resultan útiles.",
        state,
        [],
    )

    assert plan is not None
    assert plan["tool_name"] == "read_file"
    assert plan["arguments"] == {"path": "/tmp/demo.pdf", "preview": True}


def test_rule_based_plan_uses_find_local_for_named_folder_and_book(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)
    prompt = (
        'busca el archivo dentro de la carpeta "la grasa" '
        'y ahi busca el libro "la clavicula de salomon", '
        "hazme un resumen de 10 lineas"
    )

    plan = agent._rule_based_plan(prompt, state, [])

    assert plan is not None
    assert plan["tool_name"] == "find_local"
    assert plan["arguments"] == {
        "query": "la clavicula de salomon",
        "folder_hint": "la grasa",
        "kind": "file",
        "max_results": 5,
    }


def test_rule_based_plan_reads_first_match_after_find_local(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)
    prompt = (
        'busca el archivo dentro de la carpeta "la grasa" '
        'y ahi busca el libro "la clavicula de salomon", '
        "hazme un resumen de 10 lineas"
    )
    target_path = (
        "/Users/pabloalcocer/Desktop/LA GRASA/"
        "La Clavicula de Salomon.pdf"
    )
    agent._session.append(
        SessionMessage(
            role="tool",
            name="find_local",
            content=json.dumps(
                {
                    "query": "la clavicula de salomon",
                    "matches": [
                        {
                            "path": target_path,
                            "name": "La Clavicula de Salomon.pdf",
                            "is_dir": False,
                            "score": 21,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
        )
    )

    plan = agent._rule_based_plan(prompt, state, ["find_local"])

    assert plan is not None
    assert plan["tool_name"] == "read_file"
    assert plan["arguments"] == {"path": target_path, "preview": True}


def test_rule_based_plan_lists_related_documents_from_recent_folder(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)
    agent._session.append(
        SessionMessage(
            role="tool",
            name="read_file",
            content=json.dumps(
                {
                    "path": "/Users/pabloalcocer/Desktop/LA GRASA/La Clavicula de Salomon.pdf",
                    "content": "contenido del libro",
                },
                ensure_ascii=False,
            ),
        )
    )

    plan = agent._rule_based_plan(
        'busca en la carpeta "la grasa" otros libros parecidos a este',
        state,
        [],
    )

    assert plan is not None
    assert plan["tool_name"] == "list_dir"
    assert plan["arguments"] == {
        "path": "/Users/pabloalcocer/Desktop/LA GRASA",
        "depth": 2,
    }


def test_rule_based_plan_routes_web_grounded_document_compare_to_web_search(
    tmp_path: Path,
) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)

    plan = agent._rule_based_plan(
        "busca qué es la clavicula de salomon en fuentes fiables y compáralo con este libro",
        state,
        [],
    )

    assert plan is not None
    assert plan["tool_name"] == "web_search"
    assert plan["arguments"] == {"query": "clavicula salomon", "n": 5}


def test_rule_based_plan_fetches_first_web_source_after_search_for_compare(
    tmp_path: Path,
) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)
    agent._session.append(
        SessionMessage(
            role="tool",
            name="web_search",
            content=json.dumps(
                {
                    "query": "clavicula salomon",
                    "results": [
                        {
                            "title": "Wikipedia",
                            "url": "https://en.wikipedia.org/wiki/Clavicula_Salomonis_Regis",
                            "snippet": "wiki",
                        },
                        {
                            "title": "Britannica",
                            "url": "https://www.britannica.com/topic/Key-of-Solomon",
                            "snippet": "descripcion",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
        )
    )

    plan = agent._rule_based_plan(
        "busca qué es la clavicula de salomon en fuentes fiables y compáralo con este libro",
        state,
        ["web_search"],
    )

    assert plan is not None
    assert plan["tool_name"] == "web_fetch"
    assert plan["arguments"] == {
        "url": "https://www.britannica.com/topic/Key-of-Solomon"
    }


def test_rule_based_plan_fetches_next_web_source_when_more_grounding_is_needed(
    tmp_path: Path,
) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)
    agent._session.append(
        SessionMessage(
            role="tool",
            name="web_search",
            content=json.dumps(
                {
                    "query": "clavicula salomon",
                    "results": [
                        {
                            "title": "Wikipedia",
                            "url": "https://en.wikipedia.org/wiki/Clavicula_Salomonis_Regis",
                            "snippet": "uno",
                        },
                        {
                            "title": "Britannica",
                            "url": "https://www.britannica.com/topic/Key-of-Solomon",
                            "snippet": "dos",
                        },
                    ],
                },
                ensure_ascii=False,
            ),
        )
    )
    agent._session.append(
        SessionMessage(
            role="tool",
            name="web_fetch",
            content=json.dumps(
                {
                    "url": "https://en.wikipedia.org/wiki/Clavicula_Salomonis_Regis",
                    "text": "fuente 1",
                },
                ensure_ascii=False,
            ),
        )
    )

    plan = agent._rule_based_plan(
        "busca qué es la clavicula de salomon en fuentes fiables y compáralo con este libro",
        state,
        ["web_search", "web_fetch"],
    )

    assert plan is not None
    assert plan["tool_name"] == "web_fetch"
    assert plan["arguments"] == {
        "url": "https://www.britannica.com/topic/Key-of-Solomon"
    }


def test_rule_based_plan_skips_failed_web_source_and_tries_next_one(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)
    agent._session.append(
        SessionMessage(
            role="tool",
            name="web_search",
            content=json.dumps(
                {
                    "query": "clavicula salomon",
                    "results": [
                        {
                            "title": "Wikipedia",
                            "url": "https://en.wikipedia.org/wiki/Clavicula_Salomonis_Regis",
                            "snippet": "uno",
                        },
                        {
                            "title": "Britannica",
                            "url": "https://www.britannica.com/topic/Key-of-Solomon",
                            "snippet": "dos",
                        },
                    ],
                },
                ensure_ascii=False,
            ),
        )
    )
    agent._session.append(
        SessionMessage(
            role="tool",
            name="web_fetch",
            content=json.dumps(
                {
                    "url": "https://en.wikipedia.org/wiki/Clavicula_Salomonis_Regis",
                    "error": "timeout",
                },
                ensure_ascii=False,
            ),
        )
    )

    plan = agent._rule_based_plan(
        "busca qué es la clavicula de salomon en fuentes fiables y compáralo con este libro",
        state,
        ["web_search", "web_fetch"],
    )

    assert plan is not None
    assert plan["tool_name"] == "web_fetch"
    assert plan["arguments"] == {
        "url": "https://www.britannica.com/topic/Key-of-Solomon"
    }


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


def test_capability_query_returns_deterministic_overview_even_inside_repo(tmp_path: Path) -> None:
    agent = Agent(
        llm=FakeLLM(),  # type: ignore[arg-type]
        system_prompt="system",
        session=SessionStore(tmp_path),
        project_root=tmp_path,
        context_provider=lambda: RuntimeContext(
            cwd=tmp_path,
            now=datetime(2026, 4, 26, 14, 41),
            git=GitContext(
                repo_root=tmp_path,
                branch="codex/test",
                dirty=True,
                changed_files=31,
                changed_paths=["src/app.py"],
            ),
            working_set=WorkingSet(
                project_root=tmp_path,
                project_name="demo",
                markers=["pyproject.toml"],
                top_entries=["src/", "README.md"],
            ),
            active_profile="coding",
        ),
        extra_tools=_build_agent(tmp_path)._tools.values(),
    )

    result = agent.run_turn("que puedes hacer ?")

    assert result.reply != "respuesta del modelo"
    assert "leer archivos, carpetas y documentos locales" in result.reply
    assert "revisar Gmail, Google Calendar y Drive" in result.reply
    assert "automatizar páginas web" in result.reply
    assert "`demo` con 31 cambios" in result.reply


def test_self_memory_query_without_memories_returns_direct_answer(tmp_path: Path) -> None:
    agent = Agent(
        llm=FakeLLM(),  # type: ignore[arg-type]
        system_prompt="system",
        session=SessionStore(tmp_path),
        project_root=tmp_path,
        memory_store=FakeMemoryStore(count=0),  # type: ignore[arg-type]
        extra_tools=_build_agent(tmp_path)._tools.values(),
    )

    result = agent.run_turn("que sabes ya de mis intereses actuales ?")

    assert "no tengo recuerdos persistentes claros" in result.reply.lower()
    assert "revisando entradas" not in result.reply.lower()
    assert "¿te gustaría explorar" not in result.reply.lower()


def test_self_memory_query_with_memories_returns_memory_summary(tmp_path: Path) -> None:
    records = [
        type(
            "Record",
            (),
            {
                "content": "Estás investigando grimorios, simbolismo y textos esotéricos.",
                "tags": ["intereses"],
                "memory_type": "fact",
                "namespace": "general",
            },
        )()
    ]
    agent = Agent(
        llm=FakeLLM(),  # type: ignore[arg-type]
        system_prompt="system",
        session=SessionStore(tmp_path),
        project_root=tmp_path,
        memory_store=FakeMemoryStore(records=records),  # type: ignore[arg-type]
        extra_tools=_build_agent(tmp_path)._tools.values(),
    )

    result = agent.run_turn("que sabes ya de mis intereses actuales ?")

    assert "esto es lo que tengo ahora mismo en memoria" in result.reply.lower()
    assert "grimorios" in result.reply.lower()


def test_memory_capture_query_saves_memory_and_confirms(tmp_path: Path) -> None:
    store = FakeMemoryStore(count=0)
    agent = Agent(
        llm=FakeLLM(),  # type: ignore[arg-type]
        system_prompt="system",
        session=SessionStore(tmp_path),
        project_root=tmp_path,
        memory_store=store,  # type: ignore[arg-type]
        extra_tools=_build_agent(tmp_path)._tools.values(),
    )

    result = agent.run_turn(
        "recuerda que ahora estoy investigando grimorios, simbolismo y textos esotéricos"
    )

    assert "he guardado esto en memoria" in result.reply.lower()
    assert "grimorios" in result.reply.lower()
    assert store.saved_records
    assert "grimorios" in store.saved_records[0].content.lower()


def test_self_memory_query_uses_persisted_fallback_matches(tmp_path: Path) -> None:
    records = [
        type(
            "Record",
            (),
            {
                "id": 1,
                "content": "Ahora estás investigando grimorios, simbolismo y textos esotéricos.",
                "tags": ["intereses", "perfil"],
                "memory_type": "preference",
                "namespace": "general",
            },
        )()
    ]
    store = FakeMemoryStore(records=records, count=1)
    agent = Agent(
        llm=FakeLLM(),  # type: ignore[arg-type]
        system_prompt="system",
        session=SessionStore(tmp_path),
        project_root=tmp_path,
        memory_store=store,  # type: ignore[arg-type]
        extra_tools=_build_agent(tmp_path)._tools.values(),
    )

    result = agent.run_turn("que sabes ya de mis intereses actuales ?")

    assert "esto es lo que tengo ahora mismo en memoria" in result.reply.lower()
    assert "grimorios" in result.reply.lower()


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


def test_prepare_turn_state_skips_memory_and_knowledge_for_direct_file_request(
    tmp_path: Path,
) -> None:
    agent = Agent(
        llm=FakeLLM(),  # type: ignore[arg-type]
        system_prompt="system",
        session=SessionStore(tmp_path),
        project_root=tmp_path,
        memory_store=ExplodingMemoryStore(),  # type: ignore[arg-type]
        knowledge_store=ExplodingKnowledgeStore(),  # type: ignore[arg-type]
        extra_tools=_build_agent(tmp_path)._tools.values(),
    )

    state = agent._prepare_turn_state(
        "resume este PDF\n\nAdjuntos disponibles:\n- /tmp/demo.pdf\n\nÁbrelos si resultan útiles."
    )

    assert state.memories == []
    assert state.knowledge_hits == []
    assert state.knowledge_search_result is None


def test_prepare_turn_state_skips_memory_and_knowledge_for_local_file_search_request(
    tmp_path: Path,
) -> None:
    agent = Agent(
        llm=FakeLLM(),  # type: ignore[arg-type]
        system_prompt="system",
        session=SessionStore(tmp_path),
        project_root=tmp_path,
        memory_store=ExplodingMemoryStore(),  # type: ignore[arg-type]
        knowledge_store=ExplodingKnowledgeStore(),  # type: ignore[arg-type]
        extra_tools=_build_agent(tmp_path)._tools.values(),
    )

    prompt = (
        'busca el archivo dentro de la carpeta "la grasa" '
        'y ahi busca el libro "la clavicula de salomon", '
        "hazme un resumen de 10 lineas"
    )
    state = agent._prepare_turn_state(prompt)

    assert state.memories == []
    assert state.knowledge_hits == []
    assert state.knowledge_search_result is None


def test_prepare_turn_state_skips_memory_and_knowledge_for_recent_document_note_request(
    tmp_path: Path,
) -> None:
    agent = Agent(
        llm=FakeLLM(),  # type: ignore[arg-type]
        system_prompt="system",
        session=SessionStore(tmp_path),
        project_root=tmp_path,
        memory_store=ExplodingMemoryStore(),  # type: ignore[arg-type]
        knowledge_store=ExplodingKnowledgeStore(),  # type: ignore[arg-type]
        extra_tools=_build_agent(tmp_path)._tools.values(),
    )

    state = agent._prepare_turn_state(
        "crea una nota con el resumen de este libro"
    )

    assert state.memories == []
    assert state.knowledge_hits == []
    assert state.knowledge_search_result is None


def test_prepare_turn_state_skips_memory_and_knowledge_for_related_documents_request(
    tmp_path: Path,
) -> None:
    agent = Agent(
        llm=FakeLLM(),  # type: ignore[arg-type]
        system_prompt="system",
        session=SessionStore(tmp_path),
        project_root=tmp_path,
        memory_store=ExplodingMemoryStore(),  # type: ignore[arg-type]
        knowledge_store=ExplodingKnowledgeStore(),  # type: ignore[arg-type]
        extra_tools=_build_agent(tmp_path)._tools.values(),
    )

    state = agent._prepare_turn_state(
        'busca en la carpeta "la grasa" otros libros parecidos a este'
    )

    assert state.memories == []
    assert state.knowledge_hits == []
    assert state.knowledge_search_result is None


def test_prepare_turn_state_skips_memory_and_knowledge_for_web_document_compare_request(
    tmp_path: Path,
) -> None:
    agent = Agent(
        llm=FakeLLM(),  # type: ignore[arg-type]
        system_prompt="system",
        session=SessionStore(tmp_path),
        project_root=tmp_path,
        memory_store=ExplodingMemoryStore(),  # type: ignore[arg-type]
        knowledge_store=ExplodingKnowledgeStore(),  # type: ignore[arg-type]
        extra_tools=_build_agent(tmp_path)._tools.values(),
    )

    state = agent._prepare_turn_state(
        "busca qué es la clavicula de salomon en fuentes fiables y compáralo con este libro"
    )

    assert state.memories == []
    assert state.knowledge_hits == []
    assert state.knowledge_search_result is None


def test_deterministic_document_response_uses_compact_prompt(tmp_path: Path) -> None:
    llm = RecordingLLM()
    agent = Agent(
        llm=llm,  # type: ignore[arg-type]
        system_prompt="system",
        session=SessionStore(tmp_path),
        project_root=tmp_path,
        extra_tools=_build_agent(tmp_path)._tools.values(),
    )

    payload = {
        "path": "/tmp/demo.pdf",
        "content": ("Introducción. " * 1200) + ("Cierre. " * 300),
    }
    chunks: list[str] = []
    prompt = (
        "resume este PDF\n\n"
        "Adjuntos disponibles:\n"
        "- /tmp/demo.pdf\n\n"
        "Ábrelos si resultan útiles."
    )
    response = agent._deterministic_document_response(
        user_input=prompt,
        tool_name="read_file",
        payload=payload,
        on_chunk=chunks.append,
    )

    assert response is not None
    assert response.text.startswith("resumen listo")
    assert chunks[0] == "resumen listo"
    assert llm.messages is not None
    rendered_prompt = llm.messages[0].content
    assert "Ruta del documento: /tmp/demo.pdf" in rendered_prompt
    assert "[... contenido intermedio omitido para agilizar el resumen ...]" in rendered_prompt


def test_deterministic_related_documents_response_lists_candidates(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    agent._session.append(
        SessionMessage(
            role="tool",
            name="read_file",
            content=json.dumps(
                {
                    "path": "/Users/pabloalcocer/Desktop/LA GRASA/La Clavicula de Salomon.pdf",
                    "content": "contenido del libro",
                },
                ensure_ascii=False,
            ),
        )
    )

    response = agent._deterministic_related_documents_response(
        user_input='busca en la carpeta "la grasa" otros libros parecidos a este',
        tool_name="list_dir",
        payload={
            "path": "/Users/pabloalcocer/Desktop/LA GRASA",
            "entries": [
                "La Clavicula de Salomon.pdf",
                "Goetia Menor.pdf",
                "Grimorio de Honorio.pdf",
                "notas/",
            ],
        },
    )

    assert response is not None
    assert "Goetia Menor.pdf" in response.text
    assert "Grimorio de Honorio.pdf" in response.text


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


def test_response_confidence_web_answer_with_multiple_tools_is_not_low() -> None:
    confidence = summarize_response_confidence(
        knowledge_eval=None,
        successful_tools=2,
        failed_tools=1,
        used_local_knowledge=False,
    )

    assert confidence.level == "media"


def test_build_confidence_block_uses_multiple_web_citations_to_avoid_low(
    tmp_path: Path,
) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)
    block = agent._build_confidence_block(
        state=state,
        tool_observations=[
            ToolObservation(
                name="web_search",
                summary="web_search: 3 resultados",
                success=True,
                citations=(
                    "Britannica | https://www.britannica.com/topic/Key-of-Solomon",
                    "Archive | https://archive.org/details/keyofsolomon",
                    "Sacred Texts | https://www.sacred-texts.com/grim/kos/index.htm",
                ),
            ),
            ToolObservation(
                name="web_fetch",
                summary="web_fetch: error",
                success=False,
                citations=(),
            ),
        ],
    )

    assert "Britannica" in block
    assert "Archive" in block
    assert "confianza: media" in block


def test_inspect_turn_exposes_local_knowledge_signals(tmp_path: Path) -> None:
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

    agent._prepare_turn_state = lambda _user_input: state  # type: ignore[method-assign]
    inspection = agent.inspect_turn("resume el roadmap acme")

    assert inspection.intent == "assistant"
    assert inspection.profile == "general"
    assert inspection.knowledge_eval is not None
    assert inspection.local_knowledge_hits == ("roadmap-acme.md",)


def test_specialized_meeting_prep_response_renders_structured_brief(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)
    agent._session.append(  # type: ignore[attr-defined]
        SessionMessage(
            role="tool",
            name="gcal_list_events",
            content=json.dumps(
                {
                    "events": [
                        {
                            "summary": "Reunión ACME",
                            "start": "2026-04-29T10:00:00+02:00",
                            "description": "Revisar propuesta y próximos hitos",
                            "location": "Meet",
                        }
                    ]
                }
            ),
        )
    )
    agent._session.append(  # type: ignore[attr-defined]
        SessionMessage(
            role="tool",
            name="gmail_search",
            content=json.dumps(
                {
                    "messages": [
                        {
                            "subject": "ACME - feedback de propuesta",
                            "from": "ana@acme.com",
                            "date": "Mon, 27 Apr 2026 09:00:00 +0200",
                            "snippet": "Necesitamos cerrar la prioridad del sprint.",
                        }
                    ]
                }
            ),
        )
    )

    response = agent._specialized_final_response(
        user_input="prepárame la reunión de acme de mañana",
        state=state,
        tool_observations=[],
    )

    assert response is not None
    assert "ADV ARCHON meeting prep" in response.text
    assert "Reunión ACME" in response.text
    assert "ACME - feedback de propuesta" in response.text


def test_rule_based_plan_routes_gmail_draft_after_read_thread(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)
    agent._session.append(  # type: ignore[attr-defined]
        SessionMessage(
            role="tool",
            name="gmail_read_thread",
            content=json.dumps(
                {
                    "thread_id": "thread-1",
                    "messages": [
                        {
                            "from": "cliente@acme.com",
                            "to": "pablo@example.com",
                            "subject": "Revisión de propuesta",
                            "date": "Mon, 27 Apr 2026 09:00:00 +0200",
                            "snippet": "¿Puedes responder hoy?",
                            "body_excerpt": "¿Puedes responder hoy con la versión final?",
                        }
                    ],
                }
            ),
        )
    )

    plan = agent._rule_based_plan(
        "hazme triage del gmail y redacta una respuesta",
        state,
        ["gmail_search", "gmail_read_thread"],
    )

    assert plan is not None
    assert plan["tool_name"] == "gmail_draft"
    assert plan["arguments"]["to"] == ["cliente@acme.com"]


def test_specialized_study_partner_response_uses_latest_document(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)
    agent._session.append(  # type: ignore[attr-defined]
        SessionMessage(
            role="tool",
            name="read_file",
            content=json.dumps(
                {
                    "path": "/tmp/nota-salomon.pdf",
                    "content": (
                        "La clavicula de Salomon es un grimorio atribuido a la tradición "
                        "salomónica. El texto describe jerarquías, sellos y rituales."
                    ),
                }
            ),
        )
    )

    response = agent._specialized_final_response(
        user_input="actúa como study partner sobre este libro",
        state=state,
        tool_observations=[],
    )

    assert response is not None
    assert "Study partner guide" in response.text
    assert "Preguntas de repaso" in response.text


def test_specialized_executive_brief_response_combines_calendar_and_inbox(
    tmp_path: Path,
) -> None:
    agent = _build_agent(tmp_path)
    state = _build_state(tmp_path)
    agent._session.append(  # type: ignore[attr-defined]
        SessionMessage(
            role="tool",
            name="calendar_upcoming",
            content=json.dumps(
                {
                    "events": [
                        {
                            "summary": "Reunión ACME",
                            "start": "2026-04-29T10:00:00+02:00",
                            "end": "2026-04-29T11:00:00+02:00",
                            "description": "Revisión de propuesta",
                        }
                    ]
                }
            ),
        )
    )
    agent._session.append(  # type: ignore[attr-defined]
        SessionMessage(
            role="tool",
            name="gmail_search",
            content=json.dumps(
                {
                    "messages": [
                        {
                            "id": "m-1",
                            "thread_id": "t-1",
                            "from": "ana@acme.com",
                            "subject": "Contrato urgente",
                            "snippet": "Necesito respuesta hoy",
                            "date": "2026-04-28T09:00:00+02:00",
                            "label_ids": ["UNREAD"],
                        }
                    ]
                }
            ),
        )
    )

    response = agent._specialized_final_response(
        user_input="dame un briefing ejecutivo del día",
        state=state,
        tool_observations=[],
    )

    assert response is not None
    assert "ADV ARCHON executive brief" in response.text
    assert "Inbox:" in response.text
    assert "Próxima reunión:" in response.text
    assert "Contrato urgente" in response.text


def test_parse_plan_repairs_argument_types_from_model_text(tmp_path: Path) -> None:
    agent = _build_agent(tmp_path)

    plan = agent._parse_plan(
        "Claro. "
        '{"kind":"tool","tool_name":"gcal_list_events",'
        '"arguments":{"days":"7","max_results":"5","start_offset_days":"1"},'
        '"step_summary":"revisar agenda"}'
    )

    assert plan["tool_name"] == "gcal_list_events"
    assert plan["arguments"]["days"] == 7
    assert plan["arguments"]["max_results"] == 5
    assert plan["arguments"]["start_offset_days"] == 1
