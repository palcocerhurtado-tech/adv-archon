from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal, Protocol

from adv_archon.core.config import LLMConfig
from adv_archon.core.llm_types import LLMMessage, LLMResponse, LLMUsage
from adv_archon.core.privacy import PIIRedactionSession, PIIRedactor
from adv_archon.integrations.gemini import GeminiClient
from adv_archon.integrations.ollama import OllamaClient

ProviderMode = Literal["cloud", "local"]
TaskKind = Literal[
    "assistant",
    "browser",
    "coding",
    "documents",
    "fast",
    "general",
    "planner",
    "reasoning",
    "study",
    "web",
]


class ProviderClient(Protocol):
    def complete(
        self,
        messages: Iterable[LLMMessage],
        *,
        system_prompt: str,
        response_mime_type: str | None = None,
    ) -> tuple[str, LLMUsage]: ...

    def stream_complete(
        self,
        messages: Iterable[LLMMessage],
        *,
        system_prompt: str,
        on_chunk: Callable[[str], None] | None = None,
    ) -> tuple[str, LLMUsage]: ...


@dataclass(frozen=True, slots=True)
class _ResolvedRoute:
    mode: ProviderMode
    provider_name: str
    model: str
    client: ProviderClient


class LLMRouter:
    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        self._pii_redactor = PIIRedactor()
        self._mode_overrides: deque[ProviderMode] = deque()

    @property
    def mode(self) -> ProviderMode:
        if self._mode_overrides:
            return self._mode_overrides[-1]
        return "local" if self._config.mode == "local" else "cloud"

    @property
    def tool_call_repair_enabled(self) -> bool:
        return self._config.tool_call_repair

    def set_mode(self, mode: ProviderMode) -> None:
        self._config.mode = mode

    def set_ollama_model(self, model: str) -> None:
        model = model.strip()
        if not model:
            raise ValueError("El modelo de Ollama no puede estar vacío.")
        self._config.ollama_model = model

    @contextmanager
    def temporary_mode(self, mode: ProviderMode) -> Iterator[None]:
        self._mode_overrides.append(mode)
        try:
            yield
        finally:
            self._mode_overrides.pop()

    def complete(
        self,
        messages: Iterable[LLMMessage],
        *,
        system_prompt: str,
        response_mime_type: str | None = None,
        task: TaskKind | None = None,
        prefer_local: bool | None = None,
    ) -> LLMResponse:
        prepared = self._prepare_request(messages, system_prompt=system_prompt)
        route = self._resolve_route(task=task, prefer_local=prefer_local)
        text, usage = route.client.complete(
            prepared.messages,
            system_prompt=prepared.system_prompt,
            response_mime_type=response_mime_type,
        )
        usage = self._estimate_cost(usage)
        return LLMResponse(
            text=prepared.restore(text),
            usage=usage,
            provider=route.provider_name,
            model=route.model,
            redaction_applied=prepared.applied,
            redaction_items=prepared.items,
        )

    def stream_complete(
        self,
        messages: Iterable[LLMMessage],
        *,
        system_prompt: str,
        on_chunk: Callable[[str], None] | None = None,
        task: TaskKind | None = None,
        prefer_local: bool | None = None,
    ) -> LLMResponse:
        prepared = self._prepare_request(messages, system_prompt=system_prompt)
        route = self._resolve_route(task=task, prefer_local=prefer_local)
        stream_callback = on_chunk
        if prepared.applied and on_chunk is not None:
            stream_callback = None
        text, usage = route.client.stream_complete(
            prepared.messages,
            system_prompt=prepared.system_prompt,
            on_chunk=stream_callback,
        )
        usage = self._estimate_cost(usage)
        restored_text = prepared.restore(text)
        if prepared.applied and on_chunk is not None and restored_text:
            on_chunk(restored_text)
        return LLMResponse(
            text=restored_text,
            usage=usage,
            provider=route.provider_name,
            model=route.model,
            redaction_applied=prepared.applied,
            redaction_items=prepared.items,
        )

    def _provider(self, mode: ProviderMode, *, model: str) -> ProviderClient:
        if mode == "cloud":
            if not self._config.gemini_api_key:
                raise RuntimeError(
                    "No Gemini API key found. "
                    "Set GEMINI_API_KEY in ~/.adv-archon/.env or switch to /mode local."
                )
            return GeminiClient(
                api_key=self._config.gemini_api_key,
                model=model,
                temperature=self._config.temperature,
                timeout=float(self._config.gemini_timeout_seconds),
            )
        return OllamaClient(
            base_url=self._config.ollama_base_url,
            model=model,
            temperature=self._config.temperature,
            timeout=float(self._config.ollama_timeout_seconds),
            num_ctx=self._config.ollama_num_ctx,
            keep_alive=self._config.ollama_keep_alive,
        )

    def _resolve_route(
        self,
        *,
        task: TaskKind | None,
        prefer_local: bool | None,
    ) -> _ResolvedRoute:
        mode = self._resolved_mode(task=task, prefer_local=prefer_local)
        model = self._model_for_task(mode=mode, task=task)
        provider_name = "gemini" if mode == "cloud" else "ollama"
        return _ResolvedRoute(
            mode=mode,
            provider_name=provider_name,
            model=model,
            client=self._provider(mode, model=model),
        )

    def _resolved_mode(
        self,
        *,
        task: TaskKind | None,
        prefer_local: bool | None,
    ) -> ProviderMode:
        if prefer_local is True:
            return "local"
        if not self._config.task_routing_enabled:
            return self.mode
        if task in {"coding", "documents", "fast", "planner", "reasoning", "study"}:
            return "local"
        return self.mode

    def _model_for_task(self, *, mode: ProviderMode, task: TaskKind | None) -> str:
        if not self._config.task_routing_enabled:
            return self._config.gemini_model if mode == "cloud" else self._config.ollama_model

        if mode == "local":
            mapping = {
                "coding": self._config.coding_local_model,
                "documents": self._config.document_local_model,
                "fast": self._config.fast_local_model,
                "planner": self._config.planner_local_model,
                "reasoning": self._config.reasoning_local_model or self._config.coding_local_model,
                "study": self._config.document_local_model,
            }
            return mapping.get(task or "general") or self._config.ollama_model

        mapping = {
            "coding": self._config.coding_cloud_model,
            "documents": self._config.document_cloud_model,
            "fast": self._config.fast_cloud_model,
            "planner": self._config.planner_cloud_model,
            "study": self._config.document_cloud_model,
        }
        return mapping.get(task or "general") or self._config.gemini_model

    def _estimate_cost(self, usage: LLMUsage) -> LLMUsage:
        if usage.total_tokens == 0:
            usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
        if self.mode == "cloud":
            usage.estimated_cost_usd = round((usage.total_tokens / 1_000_000) * 0.3, 6)
        return usage

    def _prepare_request(
        self,
        messages: Iterable[LLMMessage],
        *,
        system_prompt: str,
    ) -> _PreparedRequest:
        frozen_messages = list(messages)
        if self.mode != "cloud" or not self._config.redact_cloud_pii:
            return _PreparedRequest(
                messages=frozen_messages,
                system_prompt=system_prompt,
                session=None,
                applied=False,
                items=0,
            )

        session = PIIRedactionSession(self._pii_redactor)
        prepared_messages: list[LLMMessage] = []
        for message in frozen_messages:
            prepared_messages.append(
                LLMMessage(role=message.role, content=session.redact(message.content))
            )
        redacted_prompt = session.redact(system_prompt)
        return _PreparedRequest(
            messages=prepared_messages,
            system_prompt=redacted_prompt,
            session=session,
            applied=bool(session.replacements),
            items=len(session.replacements),
        )


class _PreparedRequest:
    def __init__(
        self,
        *,
        messages: list[LLMMessage],
        system_prompt: str,
        session: PIIRedactionSession | None,
        applied: bool,
        items: int,
    ) -> None:
        self.messages = messages
        self.system_prompt = system_prompt
        self.session = session
        self.applied = applied
        self.items = items

    def restore(self, text: str) -> str:
        if self.session is None:
            return text
        return self.session.restore(text)
