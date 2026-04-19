from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adv_archon.core.context import RuntimeContext
from adv_archon.core.llm import LLMRouter
from adv_archon.core.llm_types import LLMMessage, LLMResponse
from adv_archon.core.memory import MemoryStore
from adv_archon.core.session import SessionMessage, SessionStore
from adv_archon.tools.files import list_dir, read_file
from adv_archon.tools.memory_tools import MemoryTools
from adv_archon.tools.web import web_fetch, web_search

ToolFn = Callable[..., Any]
ToolCallback = Callable[[str, dict[str, Any]], None]
ChunkCallback = Callable[[str], None]
ContextProvider = Callable[[], RuntimeContext]
UsageCallback = Callable[[str, LLMResponse], None]


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


class Agent:
    def __init__(
        self,
        *,
        llm: LLMRouter,
        system_prompt: str,
        session: SessionStore,
        project_root: Path,
        max_tool_steps: int = 4,
        context_provider: ContextProvider | None = None,
        memory_store: MemoryStore | None = None,
        usage_callback: UsageCallback | None = None,
        auto_recall_limit: int = 3,
        extra_tools: Sequence[ToolSpec] | None = None,
    ) -> None:
        self._llm = llm
        self._system_prompt = system_prompt
        self._session = session
        self._project_root = project_root
        self._max_tool_steps = max_tool_steps
        self._context_provider = context_provider
        self._memory_store = memory_store
        self._usage_callback = usage_callback
        self._auto_recall_limit = auto_recall_limit
        self._tools = {
            "read_file": ToolSpec(
                name="read_file",
                description=(
                    "Read a local file. Supports text, code, markdown, JSON, "
                    "TOML, CSV, HTML, and PDF."
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
                description="Store a stable user fact or preference in long-term memory.",
                schema={
                    "type": "object",
                    "properties": {
                        "fact": {"type": "string"},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["fact"],
                },
                fn=memory_tools.remember,
            )
            self._tools["recall"] = ToolSpec(
                name="recall",
                description="Search long-term memory for relevant user facts.",
                schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["query"],
                },
                fn=memory_tools.recall,
            )
        for tool in extra_tools or ():
            self._tools[tool.name] = tool

    def run_turn(
        self,
        user_input: str,
        *,
        on_tool: ToolCallback | None = None,
    ) -> AgentTurnResult:
        self._session.append(SessionMessage(role="user", content=user_input))
        tool_steps = 0

        while tool_steps < self._max_tool_steps:
            plan = self._plan(user_input)
            if plan["kind"] == "answer":
                response = self._final_response(user_input)
                self._session.append(SessionMessage(role="assistant", content=response.text))
                return AgentTurnResult(reply=response.text, usage=response)

            tool_name = str(plan["tool_name"])
            arguments = plan["arguments"]
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

        response = self._final_response(user_input)
        self._session.append(SessionMessage(role="assistant", content=response.text))
        return AgentTurnResult(reply=response.text, usage=response)

    def _plan(self, user_input: str) -> dict[str, Any]:
        planner_prompt = (
            f"{self._system_prompt}\n\n"
            f"{self._assistant_context(user_input)}\n\n"
            "You are deciding whether to answer directly or call one tool.\n"
            "Available tools:\n"
            f"{json.dumps(self._tool_manifest(), ensure_ascii=False, indent=2)}\n\n"
            "Return JSON only with one of these shapes:\n"
            '{"kind":"answer"}\n'
            '{"kind":"tool","tool_name":"<tool_name>","arguments":{"key":"value"}}\n'
        )
        response = self._llm.complete(
            self._build_messages(),
            system_prompt=planner_prompt,
            response_mime_type="application/json",
        )
        self._record_usage("planner", response)
        return self._parse_plan(response.text)

    def _final_response(self, user_input: str) -> LLMResponse:
        final_prompt = (
            f"{self._system_prompt}\n\n"
            f"{self._assistant_context(user_input)}\n"
            "Write the final answer for the user. "
            "Use the tool results already in the conversation when relevant."
        )
        response = self._llm.stream_complete(
            self._build_messages(),
            system_prompt=final_prompt,
        )
        self._record_usage("assistant", response)
        return response

    def stream_final_response(
        self,
        user_input: str,
        *,
        on_tool: ToolCallback | None = None,
        on_chunk: ChunkCallback | None = None,
    ) -> LLMResponse:
        self._session.append(SessionMessage(role="user", content=user_input))
        tool_steps = 0
        while tool_steps < self._max_tool_steps:
            plan = self._plan(user_input)
            if plan["kind"] == "answer":
                break

            tool_name = str(plan["tool_name"])
            arguments = plan["arguments"]
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

        final_prompt = (
            f"{self._system_prompt}\n\n"
            f"{self._assistant_context(user_input)}\n"
            "Write the final answer for the user. "
            "Use the tool results already in the conversation when relevant."
        )
        response = self._llm.stream_complete(
            self._build_messages(),
            system_prompt=final_prompt,
            on_chunk=on_chunk,
        )
        self._record_usage("assistant", response)
        self._session.append(SessionMessage(role="assistant", content=response.text))
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
            return {"kind": "answer"}
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            return {"kind": "answer"}
        if not isinstance(data, dict) or "kind" not in data:
            return {"kind": "answer"}
        return data

    def _assistant_context(self, user_input: str) -> str:
        lines = []
        if self._context_provider is not None:
            lines.append(self._context_provider().prompt_block())
        if self._memory_store is not None and self._memory_store.count() > 0:
            try:
                memories = self._memory_store.recall(
                    user_input,
                    limit=self._auto_recall_limit,
                )
            except Exception:
                memories = []
            if memories:
                memory_lines = [
                    f"- [#{record.id}] {record.content}"
                    + (f" | tags: {', '.join(record.tags)}" if record.tags else "")
                    for record in memories
                ]
                lines.append(
                    "Relevant long-term memory:\n" + "\n".join(memory_lines)
                )
        if not lines:
            return f"Current working directory: {self._project_root}"
        return "\n\n".join(lines)

    def _record_usage(self, phase: str, response: LLMResponse) -> None:
        if self._usage_callback is not None:
            self._usage_callback(phase, response)
