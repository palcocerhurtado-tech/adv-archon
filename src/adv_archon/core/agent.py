from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adv_archon.core.context import RuntimeContext
from adv_archon.core.intent import IntentAnalysis, IntentRouter
from adv_archon.core.knowledge import KnowledgeRecord, KnowledgeStore
from adv_archon.core.llm import LLMRouter
from adv_archon.core.llm_types import LLMMessage, LLMResponse
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
    next_action: str
    reasons: list[str]
    memory_hits: list[str]
    knowledge_hits: list[str]


@dataclass(slots=True)
class _TurnState:
    runtime_context: RuntimeContext | None
    intent: IntentAnalysis
    memories: list[MemoryRecord]
    knowledge_hits: list[KnowledgeRecord]


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

        while tool_steps < max_steps:
            plan = self._plan(user_input, state)
            if on_context is not None and not context_rendered:
                on_context(self._build_context_snapshot(state, plan))
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
            self._session.append(SessionMessage(role="tool", name=tool_name, content=serialized))
            tool_steps += 1

        response = self._final_response(user_input, state, on_chunk=on_chunk)
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
        if self._knowledge_store is not None and intent.needs_knowledge:
            try:
                knowledge_hits = self._knowledge_store.search(
                    user_input,
                    limit=self._auto_knowledge_limit,
                )
            except Exception:
                knowledge_hits = []

        return _TurnState(
            runtime_context=runtime_context,
            intent=intent,
            memories=memories,
            knowledge_hits=knowledge_hits,
        )

    def _plan(self, user_input: str, state: _TurnState) -> dict[str, Any]:
        planner_prompt = (
            f"{self._system_prompt}\n\n"
            f"{self._assistant_context(user_input, state)}\n\n"
            "You are ADV ARCHON's intent router and operator planner.\n"
            "Decide whether to answer directly or call exactly one tool next.\n"
            "If the task needs multiple steps, choose the best next tool only.\n"
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

    def _final_response(
        self,
        user_input: str,
        state: _TurnState,
        *,
        on_chunk: ChunkCallback | None,
    ) -> LLMResponse:
        final_prompt = (
            f"{self._system_prompt}\n\n"
            f"{self._assistant_context(user_input, state)}\n"
            "Write the final answer for the user. "
            "Use the tool results already in the conversation when relevant. "
            "When useful, mention what context you used in one short line."
        )
        response = self._llm.stream_complete(
            self._build_messages(),
            system_prompt=final_prompt,
            on_chunk=on_chunk,
        )
        self._record_usage("assistant", response)
        return response

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

    def _assistant_context(self, user_input: str, state: _TurnState) -> str:
        lines: list[str] = [
            "Intent analysis:",
            f"- Category: {state.intent.category}",
            f"- Profile: {state.intent.profile}",
            f"- Needs plan: {'yes' if state.intent.needs_plan else 'no'}",
            f"- Needs knowledge: {'yes' if state.intent.needs_knowledge else 'no'}",
            f"- Needs web: {'yes' if state.intent.needs_web else 'no'}",
            f"- Needs shell: {'yes' if state.intent.needs_shell else 'no'}",
            f"- Signals: {', '.join(state.intent.reasons)}",
        ]
        if state.runtime_context is not None:
            lines.append("")
            lines.append(state.runtime_context.prompt_block())
        if state.memories:
            lines.append("")
            lines.append("Relevant long-term memory:")
            for memory_record in state.memories:
                descriptor = f"{memory_record.memory_type}/{memory_record.namespace}"
                tags = (
                    f" | tags: {', '.join(memory_record.tags)}"
                    if memory_record.tags
                    else ""
                )
                lines.append(
                    f"- [#{memory_record.id}] ({descriptor}) "
                    f"{memory_record.content}{tags}"
                )
        if state.knowledge_hits:
            lines.append("")
            lines.append("Local knowledge hits:")
            for knowledge_record in state.knowledge_hits:
                lines.append(f"- {knowledge_record.title} | {knowledge_record.path}")
        if not state.memories and not state.knowledge_hits and state.runtime_context is None:
            lines.append("")
            lines.append(f"Current working directory: {self._project_root}")
        lines.append("")
        lines.append(f"Current user request: {user_input}")
        return "\n".join(lines)

    @staticmethod
    def _build_context_snapshot(state: _TurnState, plan: dict[str, Any]) -> TurnContextSnapshot:
        next_action = str(plan.get("step_summary") or plan.get("kind") or "reply directly")
        execution_mode = "operator" if state.intent.needs_plan else "direct"
        memory_hits = [
            f"{record.memory_type}/{record.namespace}: {record.content}"
            for record in state.memories[:3]
        ]
        knowledge_hits = [record.title for record in state.knowledge_hits[:3]]
        return TurnContextSnapshot(
            intent=state.intent.category,
            profile=state.intent.profile,
            execution_mode=execution_mode,
            next_action=next_action,
            reasons=state.intent.reasons[:4],
            memory_hits=memory_hits,
            knowledge_hits=knowledge_hits,
        )

    def _record_usage(self, phase: str, response: LLMResponse) -> None:
        if self._usage_callback is not None:
            self._usage_callback(phase, response)
