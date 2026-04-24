from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from adv_archon.core.context import RuntimeContext
from adv_archon.core.context_packets import ContextPacket, ToolObservation
from adv_archon.core.evals import (
    KnowledgeRetrievalEval,
    evaluate_knowledge_retrieval,
    summarize_response_confidence,
)
from adv_archon.core.intent import IntentAnalysis, IntentRouter
from adv_archon.core.knowledge import KnowledgeRecord, KnowledgeSearchResult, KnowledgeStore
from adv_archon.core.llm import LLMRouter
from adv_archon.core.llm_types import LLMMessage, LLMResponse, LLMUsage
from adv_archon.core.memory import MemoryRecord, MemoryStore
from adv_archon.core.session import SessionMessage, SessionStore
from adv_archon.tools.files import list_dir, read_file
from adv_archon.tools.knowledge_tools import KnowledgeTools
from adv_archon.tools.memory_tools import MemoryTools
from adv_archon.tools.web import web_fetch, web_search

ToolFn = Callable[..., Any]
ToolCallback = Callable[[str, dict[str, Any]], None]
ChunkCallback = Callable[[str], None]
ContextProvider = Callable[[], RuntimeContext]
UsageCallback = Callable[[str, LLMResponse], None]
ContextCallback = Callable[["TurnContextSnapshot"], None]
CALENDAR_KEYWORDS = {
    "calendario",
    "calendar",
    "agenda",
    "evento",
    "eventos",
    "reunion",
    "reuniones",
    "meeting",
    "meetings",
}
CALENDAR_CREATE_KEYWORDS = {
    "añade",
    "anade",
    "agrega",
    "crea",
    "crear",
    "mete",
    "programa",
}
TASK_KEYWORDS = {
    "tarea",
    "tareas",
    "pendiente",
    "pendientes",
    "recordatorio",
    "recordatorios",
}
REMINDER_CREATE_KEYWORDS = {
    "alarma",
    "alarm",
    "recordatorio",
    "recordatorios",
    "recuerdame",
    "recuérdame",
}
LIST_QUERY_KEYWORDS = {
    "dime",
    "enséñame",
    "enseña",
    "ensena",
    "lista",
    "muestra",
    "pendiente",
    "pendientes",
    "que",
    "qué",
    "revisa",
    "tengo",
    "ver",
}
SEARCH_QUERY_KEYWORDS = {
    "busca",
    "buscar",
    "encuentra",
    "localiza",
    "muéstrame",
    "muestrame",
}
MUTATION_KEYWORDS = {
    "agrega",
    "añade",
    "anade",
    "borrador",
    "crea",
    "crear",
    "envia",
    "envía",
    "escribe",
    "manda",
    "prepara",
    "programa",
    "ponme",
    "redacta",
}
MAIL_DRAFT_KEYWORDS = {
    "borrador",
    "correo",
    "email",
    "mail",
    "mensaje",
    "redacta",
}
REMINDER_APP_KEYWORDS = {
    "reminders",
    "recordatorios de apple",
    "recordatorios del mac",
}
GMAIL_KEYWORDS = {
    "gmail",
}
GOOGLE_CALENDAR_KEYWORDS = {
    "calendar de google",
    "calendario de google",
    "gcal",
    "google calendar",
}
NOTE_KEYWORDS = {
    "apunte",
    "apuntes",
    "nota",
    "notas",
    "notes",
}
NOTE_CREATE_KEYWORDS = {
    "anota",
    "anotame",
    "anótame",
    "apunta",
    "apuntame",
    "apúntame",
    "crea una nota",
    "crear una nota",
    "guarda en notas",
    "haz una nota",
    "hazme una nota",
    "ponlo en notas",
    "toma apuntes",
}
NOTE_SOURCE_KEYWORDS = {
    "archivo",
    "archivos",
    "carpeta",
    "carpetas",
    "desktop",
    "documento",
    "documentos",
    "escritorio",
    "fichero",
    "ficheros",
    "libro",
    "libros",
    "pdf",
}
VAULT_KEYWORDS = {
    "markdown",
    "obsidian",
    "vault",
}
DRIVE_KEYWORDS = {
    "drive",
    "google drive",
}
WEB_LIBRARY_KEYWORDS = {
    "biblioteca web",
    "contexto externo",
    "fuentes guardadas",
    "research library",
}
CONTACT_KEYWORDS = {
    "contacto",
    "contactos",
    "telefono",
    "teléfono",
    "email",
    "correo",
    "mail",
}
BROWSER_KEYWORDS = {
    "navega",
    "navegador",
    "browser",
    "captura",
    "screenshot",
    "formulario",
    "haz click",
    "click",
}
WEB_QUERY_KEYWORDS = {
    "actualidad",
    "busca",
    "google",
    "internet",
    "mercado",
    "noticias",
    "tendencias",
    "web",
}
STOPWORDS = {
    "a",
    "abre",
    "al",
    "apunte",
    "apuntes",
    "busca",
    "buscar",
    "calendar",
    "con",
    "contacto",
    "contactos",
    "biblioteca",
    "cuáles",
    "cuales",
    "de",
    "del",
    "dime",
    "el",
    "en",
    "gmail",
    "google",
    "esta",
    "este",
    "favor",
    "la",
    "las",
    "lista",
    "lo",
    "los",
    "mis",
    "muestra",
    "nota",
    "notas",
    "notes",
    "para",
    "pendientes",
    "qué",
    "que",
    "relacionado",
    "semana",
    "sus",
    "tu",
    "tengo",
    "todo",
    "drive",
    "externo",
    "fuentes",
    "guardadas",
    "vault",
    "ver",
    "web",
    "escritorio",
    "hazme",
    "libro",
    "sobre",
    "unos",
    "y",
}
WORD_RE = re.compile(r"[a-zA-Z0-9áéíóúüñÁÉÍÓÚÜÑ]+")
URL_RE = re.compile(r"https?://\S+")
QUOTED_PATH_RE = re.compile(r"""['"]((?:~|/)[^'"]+)['"]""")
UNQUOTED_PATH_RE = re.compile(r"((?:~|/)[^\n,;]+)")


@dataclass(slots=True)
class ToolSpec:
    name: str
    description: str
    schema: dict[str, Any]
    fn: ToolFn


@dataclass(slots=True)
class AgentTurnResult:
    reply: str
    usage: LLMResponse


@dataclass(slots=True)
class TurnContextSnapshot:
    intent: str
    profile: str
    execution_mode: str
    checkpoint: str
    reasons: list[str]
    confidence_hint: str | None
    memory_hits: list[str]
    knowledge_hits: list[str]


@dataclass(slots=True)
class _TurnState:
    runtime_context: RuntimeContext | None
    intent: IntentAnalysis
    memories: list[MemoryRecord]
    knowledge_hits: list[KnowledgeRecord]
    knowledge_search_result: KnowledgeSearchResult | None
    knowledge_eval: KnowledgeRetrievalEval | None


class Agent:
    def __init__(
        self,
        *,
        llm: LLMRouter,
        system_prompt: str,
        session: SessionStore,
        project_root: Path,
        max_tool_steps: int = 4,
        operator_max_tool_steps: int = 8,
        context_provider: ContextProvider | None = None,
        memory_store: MemoryStore | None = None,
        knowledge_store: KnowledgeStore | None = None,
        usage_callback: UsageCallback | None = None,
        auto_recall_limit: int = 3,
        auto_knowledge_limit: int = 5,
        force_local_private_context: bool = True,
        extra_tools: Sequence[ToolSpec] | None = None,
    ) -> None:
        self._llm = llm
        self._system_prompt = system_prompt
        self._session = session
        self._project_root = project_root
        self._max_tool_steps = max_tool_steps
        self._operator_max_tool_steps = operator_max_tool_steps
        self._context_provider = context_provider
        self._memory_store = memory_store
        self._knowledge_store = knowledge_store
        self._usage_callback = usage_callback
        self._auto_recall_limit = auto_recall_limit
        self._auto_knowledge_limit = auto_knowledge_limit
        self._force_local_private_context = force_local_private_context
        self._intent_router = IntentRouter()
        self._tools = {
            "read_file": ToolSpec(
                name="read_file",
                description=(
                    "Read a local file. Supports text, code, markdown, JSON, "
                    "TOML, CSV, HTML, images with OCR, and office docs."
                ),
                schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "start_line": {"type": "integer"},
                        "end_line": {"type": "integer"},
                    },
                    "required": ["path"],
                },
                fn=read_file,
            ),
            "list_dir": ToolSpec(
                name="list_dir",
                description="List the contents of a directory while ignoring noisy folders.",
                schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "depth": {"type": "integer"},
                    },
                    "required": ["path"],
                },
                fn=list_dir,
            ),
            "web_search": ToolSpec(
                name="web_search",
                description="Search the web with DuckDuckGo for up-to-date information.",
                schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "n": {"type": "integer"},
                    },
                    "required": ["query"],
                },
                fn=web_search,
            ),
            "web_fetch": ToolSpec(
                name="web_fetch",
                description="Fetch and clean the main text of a webpage.",
                schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                    },
                    "required": ["url"],
                },
                fn=web_fetch,
            ),
        }
        if self._memory_store is not None:
            memory_tools = MemoryTools(self._memory_store)
            self._tools["remember"] = ToolSpec(
                name="remember",
                description=(
                    "Store stable facts, preferences, project notes, tasks, decisions, "
                    "or people context in long-term memory."
                ),
                schema={
                    "type": "object",
                    "properties": {
                        "fact": {"type": "string"},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "memory_type": {"type": "string"},
                        "namespace": {"type": "string"},
                    },
                    "required": ["fact"],
                },
                fn=memory_tools.remember,
            )
            self._tools["recall"] = ToolSpec(
                name="recall",
                description="Search long-term memory for relevant user facts or project context.",
                schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer"},
                        "memory_type": {"type": "string"},
                        "namespace": {"type": "string"},
                    },
                    "required": ["query"],
                },
                fn=memory_tools.recall,
            )
        if self._knowledge_store is not None:
            knowledge_tools = KnowledgeTools(self._knowledge_store)
            self._tools["knowledge_search"] = ToolSpec(
                name="knowledge_search",
                description=(
                    "Search the local knowledge base built from the user's files and notes."
                ),
                schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["query"],
                },
                fn=knowledge_tools.knowledge_search,
            )
            self._tools["knowledge_index"] = ToolSpec(
                name="knowledge_index",
                description="Index local folders into the knowledge base for future retrieval.",
                schema={
                    "type": "object",
                    "properties": {
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [],
                },
                fn=knowledge_tools.knowledge_index,
            )
        for tool in extra_tools or ():
            self._tools[tool.name] = tool

    def run_turn(
        self,
        user_input: str,
        *,
        on_tool: ToolCallback | None = None,
        on_context: ContextCallback | None = None,
    ) -> AgentTurnResult:
        response = self._execute_turn(
            user_input,
            on_tool=on_tool,
            on_chunk=None,
            on_context=on_context,
        )
        return AgentTurnResult(reply=response.text, usage=response)

    def stream_final_response(
        self,
        user_input: str,
        *,
        on_tool: ToolCallback | None = None,
        on_chunk: ChunkCallback | None = None,
        on_context: ContextCallback | None = None,
    ) -> LLMResponse:
        return self._execute_turn(
            user_input,
            on_tool=on_tool,
            on_chunk=on_chunk,
            on_context=on_context,
        )

    def _execute_turn(
        self,
        user_input: str,
        *,
        on_tool: ToolCallback | None,
        on_chunk: ChunkCallback | None,
        on_context: ContextCallback | None,
    ) -> LLMResponse:
        self._session.append(SessionMessage(role="user", content=user_input))
        state = self._prepare_turn_state(user_input)
        force_local = self._should_force_local_for_turn(user_input, state)
        if state.knowledge_hits:
            serialized_hits = json.dumps(
                {
                    "query": user_input,
                    "results": [
                        {
                            "path": record.path,
                            "title": record.title,
                            "excerpt": record.excerpt,
                            "score": record.score,
                        }
                        for record in state.knowledge_hits
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            self._session.append(
                SessionMessage(
                    role="tool",
                    name="knowledge_search",
                    content=serialized_hits,
                )
            )

        max_steps = (
            self._operator_max_tool_steps
            if state.intent.needs_plan
            else self._max_tool_steps
        )
        tool_steps = 0
        context_rendered = False
        executed_tools: list[str] = []
        tool_observations: list[ToolObservation] = []

        llm_mode_context = (
            self._llm.temporary_mode("local")
            if force_local and self._llm.mode != "local"
            else nullcontext()
        )
        with llm_mode_context:
            while tool_steps < max_steps:
                plan = self._plan(user_input, state, executed_tools)
                if on_context is not None and not context_rendered:
                    packet = self._build_context_packet(
                        user_input=user_input,
                        state=state,
                        plan=plan,
                        tool_observations=tool_observations,
                    )
                    on_context(self._build_context_snapshot(packet))
                    context_rendered = True

                if plan.get("kind") == "answer":
                    break

                tool_name = str(plan.get("tool_name", ""))
                arguments = plan.get("arguments", {})
                if not isinstance(arguments, dict):
                    raise ValueError("Tool arguments must be a JSON object.")

                tool = self._tools.get(tool_name)
                if tool is None:
                    self._session.append(
                        SessionMessage(
                            role="tool",
                            name="tool_error",
                            content=f"Unknown tool requested: {tool_name}",
                        )
                    )
                    break

                if on_tool is not None:
                    on_tool(tool_name, arguments)

                try:
                    result = tool.fn(**arguments)
                    payload: dict[str, Any] = result.payload
                except Exception as exc:
                    payload = {"error": str(exc)}

                serialized = json.dumps(payload, ensure_ascii=False, indent=2)
                self._session.append(
                    SessionMessage(role="tool", name=tool_name, content=serialized)
                )
                executed_tools.append(tool_name)
                tool_steps += 1
                tool_observations.append(self._summarize_tool_observation(tool_name, payload))

                deterministic_error = self._deterministic_tool_error_response(
                    user_input=user_input,
                    tool_name=tool_name,
                    payload=payload,
                )
                if deterministic_error is not None:
                    self._session.append(
                        SessionMessage(role="assistant", content=deterministic_error.text)
                    )
                    return deterministic_error

            response = self._final_response(
                user_input,
                state,
                tool_observations=tool_observations,
                on_chunk=on_chunk,
            )
            self._session.append(SessionMessage(role="assistant", content=response.text))
            return response

    def _prepare_turn_state(self, user_input: str) -> _TurnState:
        runtime_context = self._context_provider() if self._context_provider is not None else None
        intent = self._intent_router.analyze(user_input, runtime_context)

        memories: list[MemoryRecord] = []
        if self._memory_store is not None and self._memory_store.count() > 0:
            try:
                memories = self._memory_store.context_matches(
                    user_input,
                    limit=self._auto_recall_limit,
                )
            except Exception:
                memories = []

        knowledge_hits: list[KnowledgeRecord] = []
        knowledge_search_result: KnowledgeSearchResult | None = None
        if self._knowledge_store is not None and intent.needs_knowledge:
            try:
                knowledge_search_result = self._knowledge_store.search_details(
                    user_input,
                    limit=self._auto_knowledge_limit,
                )
                knowledge_hits = knowledge_search_result.records
            except Exception:
                knowledge_hits = []
                knowledge_search_result = None

        knowledge_eval = evaluate_knowledge_retrieval(knowledge_search_result)

        return _TurnState(
            runtime_context=runtime_context,
            intent=intent,
            memories=memories,
            knowledge_hits=knowledge_hits,
            knowledge_search_result=knowledge_search_result,
            knowledge_eval=knowledge_eval,
        )

    def _plan(
        self,
        user_input: str,
        state: _TurnState,
        executed_tools: Sequence[str],
    ) -> dict[str, Any]:
        heuristic_plan = self._rule_based_plan(user_input, state, executed_tools)
        if heuristic_plan is not None:
            return heuristic_plan
        packet = self._build_context_packet(
            user_input=user_input,
            state=state,
            plan={"kind": "tool", "step_summary": "planificar siguiente paso"},
            tool_observations=[],
        )
        planner_prompt = (
            f"{self._system_prompt}\n\n"
            f"{packet.render_for_model()}\n\n"
            "You are ADV ARCHON's intent router and operator planner.\n"
            "Decide whether to answer directly or call exactly one tool next.\n"
            "If the task needs multiple steps, choose the best next tool only.\n"
            "Prefer dedicated personal-assistant tools over shell_exec whenever available.\n"
            "Keep step_summary sober, short, and operational.\n"
            "For note-taking requests about local folders, books, or files, prefer "
            "read_file, list_dir, or knowledge_search first, then create the note.\n"
            "Never use shell_exec for calendar, reminders, notes, contacts, email drafts, "
            "persistent tasks, or browser automation if there is a dedicated tool for it.\n"
            "Available tools:\n"
            f"{json.dumps(self._tool_manifest(), ensure_ascii=False, indent=2)}\n\n"
            "Return JSON only with one of these shapes:\n"
            '{"kind":"answer","step_summary":"reply directly"}\n'
            '{"kind":"tool","tool_name":"<tool_name>","arguments":{"key":"value"},'
            '"step_summary":"<short next step>"}\n'
        )
        response = self._llm.complete(
            self._build_messages(),
            system_prompt=planner_prompt,
            response_mime_type="application/json",
        )
        self._record_usage("planner", response)
        return self._parse_plan(response.text)

    def _rule_based_plan(
        self,
        user_input: str,
        state: _TurnState,
        executed_tools: Sequence[str],
    ) -> dict[str, Any] | None:
        normalized = _normalize_text(user_input)
        executed = set(executed_tools)

        wants_calendar = _contains_any(normalized, CALENDAR_KEYWORDS)
        wants_tasks = _contains_any(normalized, TASK_KEYWORDS)
        wants_reminders = _contains_any(normalized, REMINDER_APP_KEYWORDS)
        wants_reminder_creation = _contains_any(normalized, REMINDER_CREATE_KEYWORDS)
        wants_gmail = _contains_any(normalized, GMAIL_KEYWORDS)
        wants_google_calendar = _contains_any(normalized, GOOGLE_CALENDAR_KEYWORDS)
        wants_notes = _contains_any(normalized, NOTE_KEYWORDS)
        wants_note_creation = _looks_like_note_creation(normalized)
        wants_note_source = _looks_like_note_source_request(normalized)
        wants_vault = _contains_any(normalized, VAULT_KEYWORDS)
        wants_drive = _contains_any(normalized, DRIVE_KEYWORDS)
        wants_web_library = _contains_any(normalized, WEB_LIBRARY_KEYWORDS)
        wants_contacts = _contains_any(normalized, CONTACT_KEYWORDS)
        wants_browser = _contains_any(normalized, BROWSER_KEYWORDS)
        wants_web = _contains_any(normalized, WEB_QUERY_KEYWORDS)

        if (
            wants_google_calendar
            and _looks_like_calendar_lookup(normalized)
            and "gcal_list_events" in self._tools
            and "gcal_list_events" not in executed
        ):
            window = _infer_calendar_window(
                normalized,
                now=state.runtime_context.now if state.runtime_context is not None else None,
            )
            return {
                "kind": "tool",
                "tool_name": "gcal_list_events",
                "arguments": {
                    "days": window["days"],
                    "max_results": 20,
                    "start_offset_days": window["start_offset_days"],
                },
                "step_summary": "revisar google calendar",
            }

        if (
            wants_web_library
            and _looks_like_external_search(normalized)
            and "web_library_search" in self._tools
            and "web_library_search" not in executed
        ):
            return {
                "kind": "tool",
                "tool_name": "web_library_search",
                "arguments": {
                    "query": _extract_focus_query(normalized),
                    "limit": 8,
                },
                "step_summary": "buscar en biblioteca web local",
            }

        if (
            wants_web
            and _contains_any(normalized, {"guarda", "aprende", "culturiza", "culturízate"})
            and "web_library_save_search" in self._tools
            and "web_library_save_search" not in executed
        ):
            return {
                "kind": "tool",
                "tool_name": "web_library_save_search",
                "arguments": {
                    "query": _extract_focus_query(normalized),
                    "n": 5,
                },
                "step_summary": "guardar nueva busqueda en biblioteca web",
            }

        if (
            wants_gmail
            and _looks_like_external_search(normalized)
            and "gmail_search" in self._tools
            and "gmail_search" not in executed
        ):
            return {
                "kind": "tool",
                "tool_name": "gmail_search",
                "arguments": {
                    "query": _extract_focus_query(normalized),
                    "max_results": 10,
                },
                "step_summary": "buscar correos en gmail",
            }

        if (
            wants_drive
            and _looks_like_external_search(normalized)
            and "drive_search" in self._tools
            and "drive_search" not in executed
        ):
            return {
                "kind": "tool",
                "tool_name": "drive_search",
                "arguments": {
                    "query": _extract_focus_query(normalized),
                    "max_results": 10,
                },
                "step_summary": "buscar archivos en google drive",
            }

        if (
            wants_reminder_creation
            and _looks_like_reminder_creation(normalized)
            and "reminder_create" in self._tools
            and "reminder_create" not in executed
        ):
            return {
                "kind": "tool",
                "tool_name": "reminder_create",
                "arguments": _extract_reminder_create_arguments(user_input),
                "step_summary": "crear recordatorio en macos",
            }

        if (
            wants_notes
            and wants_note_creation
            and wants_note_source
            and "read_file" in self._tools
            and "read_file" not in executed
        ):
            hinted_path = _extract_path_hint(user_input)
            if hinted_path is not None and _path_looks_like_file(hinted_path):
                return {
                    "kind": "tool",
                    "tool_name": "read_file",
                    "arguments": {"path": hinted_path},
                    "step_summary": "leer material local para preparar nota",
                }

        if (
            wants_notes
            and wants_note_creation
            and wants_note_source
            and "list_dir" in self._tools
            and "list_dir" not in executed
        ):
            hinted_path = _extract_path_hint(user_input)
            if hinted_path is not None and not _path_looks_like_file(hinted_path):
                return {
                    "kind": "tool",
                    "tool_name": "list_dir",
                    "arguments": {"path": hinted_path, "depth": 2},
                    "step_summary": "revisar carpeta local para preparar nota",
                }

        if (
            wants_notes
            and wants_note_creation
            and wants_note_source
            and "knowledge_search" in self._tools
            and "knowledge_search" not in executed
        ):
            hinted_path = _extract_path_hint(user_input)
            if hinted_path is not None:
                return None
            query = _extract_focus_query(normalized)
            if query:
                return {
                    "kind": "tool",
                    "tool_name": "knowledge_search",
                    "arguments": {"query": query, "limit": 5},
                    "step_summary": "buscar material local para preparar nota",
                }

        if (
            wants_notes
            and wants_note_creation
            and not wants_note_source
            and "notes_create" in self._tools
            and "notes_create" not in executed
        ):
            return {
                "kind": "tool",
                "tool_name": "notes_create",
                "arguments": _extract_note_create_arguments(user_input),
                "step_summary": "crear nota en Notes",
            }

        if (
            wants_calendar
            and _looks_like_calendar_lookup(normalized)
            and "calendar_upcoming" in self._tools
            and "calendar_upcoming" not in executed
        ):
            window = _infer_calendar_window(
                normalized,
                now=state.runtime_context.now if state.runtime_context is not None else None,
            )
            return {
                "kind": "tool",
                "tool_name": "calendar_upcoming",
                "arguments": {
                    "days": window["days"],
                    "limit": 20,
                    "start_offset_days": window["start_offset_days"],
                },
                "step_summary": "revisar calendario",
            }

        if (
            wants_tasks
            and _looks_like_task_lookup(normalized)
            and "task_list" in self._tools
            and "task_list" not in executed
            and (not wants_calendar or "calendar_upcoming" in executed)
        ):
            return {
                "kind": "tool",
                "tool_name": "task_list",
                "arguments": {"status": "open", "limit": 20},
                "step_summary": "consultar tareas persistentes",
            }

        if (
            wants_reminders
            and _looks_like_reminders_lookup(normalized)
            and "reminders_list" in self._tools
            and "reminders_list" not in executed
        ):
            return {
                "kind": "tool",
                "tool_name": "reminders_list",
                "arguments": {"limit": 20},
                "step_summary": "consultar recordatorios del sistema",
            }

        if (
            wants_vault
            and "vault_search" in self._tools
            and "vault_search" not in executed
        ):
            query = _extract_focus_query(normalized)
            if query:
                return {
                    "kind": "tool",
                    "tool_name": "vault_search",
                    "arguments": {"query": query, "limit": 10},
                    "step_summary": "buscar en vault markdown",
                }

        if (
            wants_notes
            and not wants_vault
            and _looks_like_notes_lookup(normalized)
            and "notes_search" in self._tools
            and "notes_search" not in executed
        ):
            query = _extract_focus_query(normalized)
            if query:
                return {
                    "kind": "tool",
                    "tool_name": "notes_search",
                    "arguments": {"query": query, "limit": 10},
                    "step_summary": "buscar en notas",
                }

        if (
            wants_contacts
            and _looks_like_contacts_lookup(normalized)
            and "contacts_search" in self._tools
            and "contacts_search" not in executed
        ):
            query = _extract_focus_query(normalized)
            if query:
                return {
                    "kind": "tool",
                    "tool_name": "contacts_search",
                    "arguments": {"query": query, "limit": 10},
                    "step_summary": "buscar en contactos",
                }

        if wants_browser:
            url = _extract_url(user_input)
            if url and "browser_open" in self._tools and "browser_open" not in executed:
                return {
                    "kind": "tool",
                    "tool_name": "browser_open",
                    "arguments": {"url": url},
                    "step_summary": "abrir pagina en navegador gestionado",
                }
            if (
                ("captura" in normalized or "screenshot" in normalized)
                and "browser_screenshot" in self._tools
                and "browser_open" in executed
                and "browser_screenshot" not in executed
            ):
                return {
                    "kind": "tool",
                    "tool_name": "browser_screenshot",
                    "arguments": {},
                    "step_summary": "sacar captura del navegador",
                }

        return None

    def _final_response(
        self,
        user_input: str,
        state: _TurnState,
        *,
        tool_observations: Sequence[ToolObservation],
        on_chunk: ChunkCallback | None,
    ) -> LLMResponse:
        packet = self._build_context_packet(
            user_input=user_input,
            state=state,
            plan={"kind": "answer", "step_summary": "responder"},
            tool_observations=tool_observations,
        )
        final_prompt = (
            f"{self._system_prompt}\n\n"
            f"{packet.render_for_model()}\n\n"
            "Write the final answer for the user. "
            "Use the tool results already in the conversation when relevant. "
            "When useful, mention what context you used in one short line. "
            "Prefer grounded statements over broad claims. "
            "If local knowledge was used, stay close to the evidence. "
            "If a tool reported an error, explain it briefly and concretely. "
            "Do not claim you retried unless you actually retried. "
            "Do not ask the user whether you should retry unless the next step truly "
            "requires their confirmation or an external permission change."
        )
        response = self._llm.stream_complete(
            self._build_messages(),
            system_prompt=final_prompt,
            on_chunk=on_chunk,
        )
        response = self._append_confidence_block(
            response,
            state=state,
            tool_observations=tool_observations,
            on_chunk=on_chunk,
        )
        self._record_usage("assistant", response)
        return response

    def _deterministic_tool_error_response(
        self,
        *,
        user_input: str,
        tool_name: str,
        payload: dict[str, Any],
    ) -> LLMResponse | None:
        error = str(payload.get("error") or "").strip()
        if not error:
            return None

        normalized = _normalize_text(user_input)
        text: str | None = None

        if tool_name == "calendar_upcoming":
            period = _describe_calendar_period(normalized)
            if "timeout" in error.lower() or "tardado demasiado" in error.lower():
                text = (
                    f"No he podido consultar tu calendario para {period} porque el conector "
                    "ha tardado demasiado y se ha cancelado. "
                    "Si quieres, revisa que Calendar tenga permisos de automatizacion y "
                    "vuelve a probar."
                )
            else:
                text = (
                    f"No he podido consultar tu calendario para {period}. "
                    f"Error: {error}"
                )
        elif tool_name == "reminders_list":
            if "timeout" in error.lower() or "tardado demasiado" in error.lower():
                text = (
                    "No he podido consultar tus recordatorios porque el conector ha "
                    "tardado demasiado y se ha cancelado. "
                    "Si quieres, revisa permisos de Recordatorios y vuelve a probar."
                )
            else:
                text = f"No he podido consultar tus recordatorios. Error: {error}"

        if text is None:
            return None

        return LLMResponse(
            text=text,
            usage=LLMUsage(),
            provider="deterministic",
            model="tool-error-handler",
        )

    def _build_messages(self) -> list[LLMMessage]:
        return [
            LLMMessage(
                role="model" if message.role == "assistant" else "user",
                content=self._format_message(message),
            )
            for message in self._session.messages
        ]

    @staticmethod
    def _format_message(message: SessionMessage) -> str:
        if message.role == "tool":
            return f"Tool `{message.name}` result:\n{message.content}"
        return message.content

    def _tool_manifest(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "schema": tool.schema,
            }
            for tool in self._tools.values()
        ]

    @staticmethod
    def _parse_plan(text: str) -> dict[str, Any]:
        stripped = text.strip()
        if not stripped:
            return {"kind": "answer", "step_summary": "reply directly"}
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            return {"kind": "answer", "step_summary": "reply directly"}
        if not isinstance(data, dict) or "kind" not in data:
            return {"kind": "answer", "step_summary": "reply directly"}
        return data

    def _build_context_packet(
        self,
        *,
        user_input: str,
        state: _TurnState,
        plan: dict[str, Any],
        tool_observations: Sequence[ToolObservation],
    ) -> ContextPacket:
        runtime_block = (
            state.runtime_context.prompt_block()
            if state.runtime_context is not None
            else f"Current working directory: {self._project_root}"
        )
        memory_items = tuple(
            self._format_memory_item(record) for record in state.memories[:3]
        )
        knowledge_items = tuple(
            self._format_knowledge_item(record) for record in state.knowledge_hits[:4]
        )
        tool_items = tuple(observation.summary for observation in tool_observations[-4:])
        checkpoint = self._normalize_checkpoint(
            str(plan.get("step_summary") or plan.get("kind") or "responder")
        )
        confidence_hint = (
            self._render_knowledge_hint(state.knowledge_eval)
            if state.knowledge_eval is not None
            else None
        )
        return ContextPacket(
            task=user_input,
            intent=state.intent.category,
            profile=state.intent.profile,
            execution_mode="operator" if state.intent.needs_plan else "direct",
            checkpoint=checkpoint,
            reasons=tuple(state.intent.reasons[:4]),
            runtime_block=runtime_block,
            memory_items=memory_items,
            knowledge_items=knowledge_items,
            tool_items=tool_items,
            confidence_hint=confidence_hint,
        )

    @staticmethod
    def _build_context_snapshot(packet: ContextPacket) -> TurnContextSnapshot:
        return TurnContextSnapshot(
            intent=packet.intent,
            profile=packet.profile,
            execution_mode=packet.execution_mode,
            checkpoint=packet.checkpoint,
            reasons=list(packet.reasons),
            confidence_hint=packet.confidence_hint,
            memory_hits=list(packet.memory_items[:3]),
            knowledge_hits=list(packet.knowledge_items[:3]),
        )

    @staticmethod
    def _format_memory_item(record: MemoryRecord) -> str:
        descriptor = f"{record.memory_type}/{record.namespace}"
        tags = f" | tags: {', '.join(record.tags)}" if record.tags else ""
        return f"[#{record.id}] ({descriptor}) {record.content}{tags}"

    @staticmethod
    def _format_knowledge_item(record: KnowledgeRecord) -> str:
        score = f"{record.score:.2f}" if record.score is not None else "n/a"
        coverage = f"{record.term_coverage:.0%}" if record.term_coverage else "0%"
        return f"{record.title} | {record.path} | score={score} | coverage={coverage}"

    @staticmethod
    def _normalize_checkpoint(step_summary: str) -> str:
        lowered = step_summary.strip().lower() or "responder"
        replacements = {
            "reply directly": "responder",
            "reply": "responder",
            "answer": "responder",
        }
        lowered = replacements.get(lowered, lowered)
        words = lowered.split()
        if len(words) > 5:
            lowered = " ".join(words[:5])
        return lowered

    @staticmethod
    def _render_knowledge_hint(
        knowledge_eval: KnowledgeRetrievalEval | None,
    ) -> str | None:
        if knowledge_eval is None:
            return None
        mapping = {
            "high": "conocimiento local fuerte",
            "medium": "conocimiento local razonable",
            "low": "conocimiento local debil",
        }
        return mapping.get(knowledge_eval.confidence)

    def _summarize_tool_observation(
        self,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolObservation:
        error = str(payload.get("error") or "").strip()
        if error:
            return ToolObservation(
                name=tool_name,
                summary=f"{tool_name}: error - {error}",
                success=False,
            )

        if tool_name == "read_file":
            path = str(payload.get("path") or "archivo")
            return ToolObservation(
                name=tool_name,
                summary=f"archivo leido: {path}",
                success=True,
                citations=(path,),
            )
        if tool_name == "list_dir":
            path = str(payload.get("path") or "directorio")
            entries = payload.get("entries")
            count = len(entries) if isinstance(entries, list) else 0
            return ToolObservation(
                name=tool_name,
                summary=f"directorio listado: {path} ({count} entradas)",
                success=True,
                citations=(path,),
            )

        for key in (
            "results",
            "messages",
            "events",
            "reminders",
            "tasks",
            "notes",
            "contacts",
            "items",
        ):
            raw_items = payload.get(key)
            if isinstance(raw_items, list):
                summary, citations = self._summarize_list_tool(tool_name, raw_items)
                return ToolObservation(
                    name=tool_name,
                    summary=summary,
                    success=True,
                    citations=citations,
                )

        return ToolObservation(
            name=tool_name,
            summary=f"{tool_name}: completado",
            success=True,
        )

    @staticmethod
    def _summarize_list_tool(
        tool_name: str,
        items: list[Any],
    ) -> tuple[str, tuple[str, ...]]:
        count = len(items)
        if not items:
            return (f"{tool_name}: sin resultados", ())

        citations: list[str] = []
        first = items[0]
        if isinstance(first, dict):
            title = str(
                first.get("title")
                or first.get("summary")
                or first.get("subject")
                or first.get("name")
                or first.get("folder")
                or "resultado"
            )
            reference = str(
                first.get("path")
                or first.get("webViewLink")
                or first.get("url")
                or first.get("from")
                or title
            )
            citations.append(f"{title} | {reference}")
            return (f"{tool_name}: {count} resultados, primero {title}", tuple(citations))

        first_text = str(first)
        citations.append(first_text)
        return (f"{tool_name}: {count} resultados, primero {first_text}", tuple(citations))

    def _append_confidence_block(
        self,
        response: LLMResponse,
        *,
        state: _TurnState,
        tool_observations: Sequence[ToolObservation],
        on_chunk: ChunkCallback | None,
    ) -> LLMResponse:
        block = self._build_confidence_block(state=state, tool_observations=tool_observations)
        if not block:
            return response
        if on_chunk is not None:
            on_chunk(block)
        return LLMResponse(
            text=f"{response.text}{block}",
            usage=response.usage,
            provider=response.provider,
            model=response.model,
            redaction_applied=response.redaction_applied,
            redaction_items=response.redaction_items,
        )

    def _build_confidence_block(
        self,
        *,
        state: _TurnState,
        tool_observations: Sequence[ToolObservation],
    ) -> str:
        successful_tools = sum(1 for observation in tool_observations if observation.success)
        failed_tools = sum(1 for observation in tool_observations if not observation.success)
        confidence = summarize_response_confidence(
            knowledge_eval=state.knowledge_eval,
            successful_tools=successful_tools,
            failed_tools=failed_tools,
            used_local_knowledge=bool(state.knowledge_hits),
        )
        citations: list[str] = []
        for record in state.knowledge_hits[:2]:
            citations.append(f"conocimiento local: {record.title} | {record.path}")
        for observation in tool_observations:
            if not observation.success:
                continue
            citations.extend(f"{observation.name}: {item}" for item in observation.citations[:1])
            if len(citations) >= 4:
                break

        if not citations and confidence.level == "baja":
            return ""

        lines = ["", "", "Base y confianza:"]
        if citations:
            lines.extend(f"- {citation}" for citation in citations[:4])
        else:
            lines.append("- sin evidencia local explicita")
        lines.append(f"- confianza: {confidence.level}")
        if confidence.rationale:
            lines.append(f"- motivo: {'; '.join(confidence.rationale[:3])}")
        return "\n".join(lines)

    def _record_usage(self, phase: str, response: LLMResponse) -> None:
        if self._usage_callback is not None:
            self._usage_callback(phase, response)

    def _should_force_local_for_turn(self, user_input: str, state: _TurnState) -> bool:
        if not self._force_local_private_context:
            return False
        normalized = _normalize_text(user_input)
        if _extract_path_hint(user_input) is not None:
            return True
        if state.knowledge_hits or state.memories:
            return True
        if state.intent.category in {"assistant", "coding", "documents", "shell"}:
            return True
        private_keywords = (
            CALENDAR_KEYWORDS
            | TASK_KEYWORDS
            | REMINDER_APP_KEYWORDS
            | REMINDER_CREATE_KEYWORDS
            | NOTE_KEYWORDS
            | VAULT_KEYWORDS
            | CONTACT_KEYWORDS
            | GMAIL_KEYWORDS
            | GOOGLE_CALENDAR_KEYWORDS
            | DRIVE_KEYWORDS
        )
        return _contains_any(normalized, private_keywords)


def _normalize_text(text: str) -> str:
    return text.casefold()


def _contains_any(text: str, keywords: set[str]) -> bool:
    for keyword in keywords:
        if " " in keyword:
            if keyword in text:
                return True
            continue
        if len(keyword) <= 3:
            if re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", text):
                return True
            continue
        if keyword in text:
            return True
    return False


def _looks_like_calendar_lookup(text: str) -> bool:
    if _contains_any(text, CALENDAR_CREATE_KEYWORDS):
        return False
    return _contains_any(text, LIST_QUERY_KEYWORDS)


def _looks_like_task_lookup(text: str) -> bool:
    return _contains_any(text, LIST_QUERY_KEYWORDS) and not _contains_any(
        text, MUTATION_KEYWORDS
    )


def _looks_like_reminders_lookup(text: str) -> bool:
    return _contains_any(text, LIST_QUERY_KEYWORDS) and not _contains_any(
        text, MUTATION_KEYWORDS
    )


def _looks_like_reminder_creation(text: str) -> bool:
    return _contains_any(text, REMINDER_CREATE_KEYWORDS) and (
        _contains_any(text, MUTATION_KEYWORDS)
        or "ponme" in text
        or "recuérdame" in text
        or "recuerdame" in text
    )


def _looks_like_notes_lookup(text: str) -> bool:
    return _contains_any(text, SEARCH_QUERY_KEYWORDS | LIST_QUERY_KEYWORDS)


def _looks_like_note_creation(text: str) -> bool:
    if _contains_any(text, NOTE_CREATE_KEYWORDS):
        return True
    if _contains_any(text, {"apunte", "apuntes"}) and (
        "hazme" in text or "haz " in text or "prepara" in text
    ):
        return True
    return _contains_any(text, NOTE_KEYWORDS) and _contains_any(text, MUTATION_KEYWORDS)


def _looks_like_note_source_request(text: str) -> bool:
    return _contains_any(text, NOTE_SOURCE_KEYWORDS)


def _looks_like_external_search(text: str) -> bool:
    return _contains_any(text, SEARCH_QUERY_KEYWORDS | LIST_QUERY_KEYWORDS) and not _contains_any(
        text, MUTATION_KEYWORDS
    )


def _looks_like_contacts_lookup(text: str) -> bool:
    if _contains_any(text, MAIL_DRAFT_KEYWORDS) and _contains_any(text, MUTATION_KEYWORDS):
        return False
    return _contains_any(text, SEARCH_QUERY_KEYWORDS | LIST_QUERY_KEYWORDS)


def _infer_calendar_window(text: str, *, now: datetime | None = None) -> dict[str, int]:
    if "hoy" in text:
        return {"days": 1, "start_offset_days": 0}
    if "mañana" in text or "manana" in text:
        return {"days": 1, "start_offset_days": 1}
    if (
        "semana que viene" in text
        or "semana que entra" in text
        or "proxima semana" in text
        or "próxima semana" in text
        or "next week" in text
    ):
        if now is None:
            return {"days": 7, "start_offset_days": 7}
        return {"days": 7, "start_offset_days": 7 - now.weekday()}
    if "esta semana" in text or "this week" in text:
        if now is None:
            return {"days": 7, "start_offset_days": 0}
        return {"days": max(1, 7 - now.weekday()), "start_offset_days": 0}
    if "mes" in text:
        return {"days": 31, "start_offset_days": 0}
    match = re.search(r"(\d+)\s+d[ií]as", text)
    if match is not None:
        return {"days": max(1, int(str(match.group(1)))), "start_offset_days": 0}
    return {"days": 7, "start_offset_days": 0}


def _describe_calendar_period(text: str) -> str:
    if "hoy" in text:
        return "hoy"
    if "mañana" in text or "manana" in text:
        return "mañana"
    if (
        "semana que viene" in text
        or "semana que entra" in text
        or "proxima semana" in text
        or "próxima semana" in text
        or "next week" in text
    ):
        return "la semana que viene"
    if "esta semana" in text or "this week" in text:
        return "esta semana"
    if "mes" in text:
        return "este mes"
    return "ese periodo"


def _extract_focus_query(text: str) -> str:
    words = [match.group(0) for match in WORD_RE.finditer(text)]
    filtered = [
        word for word in words if len(word) > 2 and word.casefold() not in STOPWORDS
    ]
    return " ".join(filtered[:6])


def _extract_url(text: str) -> str | None:
    match = URL_RE.search(text)
    if match is None:
        return None
    return match.group(0)


def _extract_reminder_create_arguments(text: str) -> dict[str, Any]:
    normalized = _normalize_text(text)
    due_text, due_span = _extract_due_text(normalized)
    title = _extract_reminder_title(normalized, due_span)
    arguments: dict[str, Any] = {"title": title}
    if due_text:
        arguments["due_text"] = due_text
    return arguments


def _extract_due_text(text: str) -> tuple[str | None, tuple[int, int] | None]:
    patterns = (
        r"\b(pasado mañana|pasado manana|mañana|manana|hoy)\s+a\s+las\s+\d{1,2}(?::\d{2})?",
        r"\bel\s+(lunes|martes|miercoles|miércoles|jueves|viernes|sabado|sábado|domingo)\s+a\s+las\s+\d{1,2}(?::\d{2})?",
        r"\ba\s+las\s+\d{1,2}(?::\d{2})?",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match is None:
            continue
        due_text = match.group(0)
        if due_text.startswith("a las "):
            due_text = f"hoy {due_text}"
        return due_text, match.span()
    return None, None


def _extract_reminder_title(text: str, due_span: tuple[int, int] | None) -> str:
    working = text
    if due_span is not None:
        start, end = due_span
        working = f"{working[:start]} {working[end:]}"
    working = re.sub(
        r"\b(ponme|crea|crear|agrega|añade|anade|programa|recuérdame|recuerdame)\b",
        " ",
        working,
    )
    working = re.sub(r"\b(una|un|mi|me)\b", " ", working)
    working = re.sub(r"\b(alarma|alarm|recordatorio|recordatorios)\b", " ", working)
    match = re.search(r"\bde\s+(.+)", working)
    if match is not None:
        candidate = match.group(1).strip(" .,:;")
        if candidate:
            return candidate
    candidate = re.sub(r"\s+", " ", working).strip(" .,:;")
    if candidate:
        return candidate
    if "alarma" in text or "alarm" in text:
        return "Alarma"
    return "Recordatorio"


def _extract_note_create_arguments(text: str) -> dict[str, Any]:
    title = _extract_note_title(text)
    body = _extract_note_body(text, title)
    arguments: dict[str, Any] = {
        "title": title,
        "body": body,
    }
    folder = _extract_notes_folder(text)
    if folder is not None:
        arguments["folder"] = folder
    return arguments


def _extract_note_title(text: str) -> str:
    patterns = (
        r"titulad[ao]\s+['\"]?(.+?)['\"]?(?=$|\s+que\b|\s+con\b|\s+en\b|:)",
        r"(?:nota|apuntes?)\s+sobre\s+(.+?)(?=$|\s+que\b|\s+con\b|:)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match is None:
            continue
        candidate = match.group(1).strip(" .,:;\"'")
        if candidate:
            return candidate
    return "Apunte"


def _extract_note_body(text: str, title: str) -> str:
    colon_match = re.search(r":\s*(.+)$", text, flags=re.DOTALL)
    if colon_match is not None:
        candidate = colon_match.group(1).strip()
        if candidate:
            return candidate

    diga_match = re.search(
        r"(?:que diga|que ponga|con el texto)\s+(.+)$",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if diga_match is not None:
        candidate = diga_match.group(1).strip(" .")
        if candidate:
            return candidate

    about_match = re.search(r"sobre\s+(.+)$", text, flags=re.IGNORECASE | re.DOTALL)
    if about_match is not None:
        candidate = about_match.group(1).strip(" .")
        if candidate:
            return f"Apuntes sobre {candidate}."

    return f"Nota rápida: {title}."


def _extract_notes_folder(text: str) -> str | None:
    match = re.search(
        r"en\s+la\s+carpeta\s+['\"]?(.+?)['\"]?(?=$|\s+que\b|:)",
        text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    candidate = match.group(1).strip(" .,:;\"'")
    return candidate or None


def _extract_path_hint(text: str) -> str | None:
    quoted_match = QUOTED_PATH_RE.search(text)
    if quoted_match is not None:
        return quoted_match.group(1).strip()
    unquoted_match = UNQUOTED_PATH_RE.search(text)
    if unquoted_match is None:
        return None
    return unquoted_match.group(1).strip().rstrip(" .")


def _path_looks_like_file(path: str) -> bool:
    return Path(path).suffix != ""
