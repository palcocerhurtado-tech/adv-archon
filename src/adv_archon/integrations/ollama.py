from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass

import httpx

from adv_archon.core.llm_types import LLMMessage, LLMUsage


@dataclass(slots=True)
class OllamaClient:
    base_url: str
    model: str
    temperature: float
    timeout: float = 60.0
    num_ctx: int = 2048       # 2048 is plenty for most queries; 4x faster than 8192
    keep_alive: str = "-1"
    num_predict: int = 768    # cap output tokens — avoids runaway generation
    num_thread: int = 0       # 0 = Ollama auto-selects (all physical cores)

    def _keep_alive_value(self) -> int | str:
        return -1 if self.keep_alive.strip() == "-1" else self.keep_alive

    def _options(self) -> dict[str, object]:
        opts: dict[str, object] = {
            "temperature": self.temperature,
            "num_ctx": self.num_ctx,
            "num_predict": self.num_predict,
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
    ) -> tuple[str, LLMUsage]:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": self._build_messages(messages, system_prompt=system_prompt),
            "stream": True,
            "keep_alive": self._keep_alive_value(),
            "options": self._options(),
        }
        chunks: list[str] = []
        usage = LLMUsage()
        with httpx.Client(timeout=self.timeout) as client, client.stream(
            "POST",
            f"{self.base_url}/api/chat",
            json=payload,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
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
        return "".join(chunks), usage

    @staticmethod
    def _build_messages(
        messages: Iterable[LLMMessage],
        *,
        system_prompt: str,
    ) -> list[dict[str, str]]:
        payload = [{"role": "system", "content": system_prompt}]
        payload.extend({"role": message.role, "content": message.content} for message in messages)
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
