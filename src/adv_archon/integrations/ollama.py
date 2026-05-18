from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from threading import Event

import httpx

from adv_archon.core.llm_types import LLMMessage, LLMUsage


class OllamaCancelledError(RuntimeError):
    """Raised when a local Ollama stream is cancelled by the UI."""


class OllamaUnavailableError(RuntimeError):
    """Raised when Ollama cannot be reached before generation starts."""


@dataclass(slots=True)
class OllamaClient:
    base_url: str
    model: str
    temperature: float
    timeout: float = 60.0
    num_ctx: int = 4096        # 4096 balances context quality vs speed
    keep_alive: str = "-1"
    num_predict: int = 768     # cap output tokens — avoids runaway generation
    num_thread: int = 0        # 0 = Ollama auto-selects (all physical cores)
    num_batch: int = 512       # prompt-eval batch size — bigger = faster prefill

    def _keep_alive_value(self) -> int | str:
        return -1 if self.keep_alive.strip() == "-1" else self.keep_alive

    def _options(self) -> dict[str, object]:
        opts: dict[str, object] = {
            "temperature": self.temperature,
            "num_ctx": self.num_ctx,
            "num_predict": self.num_predict,
            "num_batch": self.num_batch,
            "top_k": 20,          # narrow sampling → faster + more focused
            "top_p": 0.85,
            "repeat_penalty": 1.1,
        }
        if self.num_thread:
            opts["num_thread"] = self.num_thread
        return opts

    def complete(
        self,
        messages: Iterable[LLMMessage],
        *,
        system_prompt: str,
        response_mime_type: str | None = None,
    ) -> tuple[str, LLMUsage]:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": self._build_messages(messages, system_prompt=system_prompt),
            "stream": False,
            "keep_alive": self._keep_alive_value(),
            "options": self._options(),
        }
        if response_mime_type == "application/json":
            payload["format"] = "json"
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
        data = response.json()
        message = data.get("message", {})
        content = message.get("content", "") if isinstance(message, dict) else ""
        return str(content), self._extract_usage(data)

    def stream_complete(
        self,
        messages: Iterable[LLMMessage],
        *,
        system_prompt: str,
        on_chunk: Callable[[str], None] | None = None,
        response_mime_type: str | None = None,
        cancel_event: Event | None = None,
    ) -> tuple[str, LLMUsage]:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": self._build_messages(messages, system_prompt=system_prompt),
            "stream": True,
            "keep_alive": self._keep_alive_value(),
            "options": self._options(),
        }
        if response_mime_type == "application/json":
            payload["format"] = "json"
        chunks: list[str] = []
        usage = LLMUsage()
        try:
            with httpx.Client(timeout=self.timeout) as client, client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if cancel_event is not None and cancel_event.is_set():
                        raise OllamaCancelledError("Generación local cancelada por el usuario.")
                    if not line:
                        continue
                    data = json.loads(line)
                    message = data.get("message", {})
                    content = message.get("content", "") if isinstance(message, dict) else ""
                    if content:
                        chunks.append(str(content))
                        if on_chunk is not None:
                            on_chunk(str(content))
                    if data.get("done"):
                        usage = self._extract_usage(data)
        except httpx.ConnectError as exc:
            raise OllamaUnavailableError(
                "No puedo conectar con Ollama. Abre Ollama.app o ejecuta `ollama serve`."
            ) from exc
        return "".join(chunks), usage

    @staticmethod
    def _build_messages(
        messages: Iterable[LLMMessage],
        *,
        system_prompt: str,
    ) -> list[dict[str, str]]:
        payload: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            # Gemini uses "model" role; Ollama API requires "assistant"
            role = "assistant" if msg.role == "model" else msg.role
            payload.append({"role": role, "content": msg.content})
        return payload

    @staticmethod
    def _extract_usage(data: dict[str, object]) -> LLMUsage:
        prompt_tokens = _coerce_int(data.get("prompt_eval_count"))
        completion_tokens = _coerce_int(data.get("eval_count"))
        return LLMUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )


def _coerce_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0
