from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from typing import Literal

from adv_archon.core.config import LLMConfig
from adv_archon.core.llm_types import LLMMessage, LLMResponse, LLMUsage
from adv_archon.core.privacy import PIIRedactionSession, PIIRedactor
from adv_archon.integrations.gemini import GeminiClient
from adv_archon.integrations.ollama import OllamaClient

ProviderMode = Literal["cloud", "local"]


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

    def set_mode(self, mode: ProviderMode) -> None:
        self._config.mode = mode

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
    ) -> LLMResponse:
        prepared = self._prepare_request(messages, system_prompt=system_prompt)
        provider = self._provider()
        text, usage = provider.complete(
            prepared.messages,
            system_prompt=prepared.system_prompt,
            response_mime_type=response_mime_type,
        )
        usage = self._estimate_cost(usage)
        provider_name, model = self._provider_name_model()
        return LLMResponse(
            text=prepared.restore(text),
            usage=usage,
            provider=provider_name,
            model=model,
            redaction_applied=prepared.applied,
            redaction_items=prepared.items,
        )

    def stream_complete(
        self,
        messages: Iterable[LLMMessage],
        *,
        system_prompt: str,
        on_chunk: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        prepared = self._prepare_request(messages, system_prompt=system_prompt)
        provider = self._provider()
        stream_callback = on_chunk
        if prepared.applied and on_chunk is not None:
            stream_callback = None
        text, usage = provider.stream_complete(
            prepared.messages,
            system_prompt=prepared.system_prompt,
            on_chunk=stream_callback,
        )
        usage = self._estimate_cost(usage)
        provider_name, model = self._provider_name_model()
        restored_text = prepared.restore(text)
        if prepared.applied and on_chunk is not None and restored_text:
            on_chunk(restored_text)
        return LLMResponse(
            text=restored_text,
            usage=usage,
            provider=provider_name,
            model=model,
            redaction_applied=prepared.applied,
            redaction_items=prepared.items,
        )

    def _provider(self) -> GeminiClient | OllamaClient:
        if self.mode == "cloud":
            if not self._config.gemini_api_key:
                raise RuntimeError(
                    "No Gemini API key found. "
                    "Set GEMINI_API_KEY in ~/.adv-archon/.env or switch to /mode local."
                )
            return GeminiClient(
                api_key=self._config.gemini_api_key,
                model=self._config.gemini_model,
                temperature=self._config.temperature,
            )
        return OllamaClient(
            base_url=self._config.ollama_base_url,
            model=self._config.ollama_model,
            temperature=self._config.temperature,
        )

    def _provider_name_model(self) -> tuple[str, str]:
        if self.mode == "cloud":
            return "gemini", self._config.gemini_model
        return "ollama", self._config.ollama_model

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
