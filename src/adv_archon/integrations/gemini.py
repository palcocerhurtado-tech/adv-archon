from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass

import httpx

from adv_archon.core.llm_types import LLMMessage, LLMUsage


@dataclass(slots=True)
class GeminiClient:
    api_key: str
    model: str
    temperature: float
    timeout: float = 60.0

    @property
    def _base_url(self) -> str:
        return "https://generativelanguage.googleapis.com/v1beta/models"

    def _build_payload(
        self,
        messages: Iterable[LLMMessage],
        *,
        system_prompt: str,
        response_mime_type: str | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [
                {"role": message.role, "parts": [{"text": message.content}]} for message in messages
            ],
            "generationConfig": {
                "temperature": self.temperature,
            },
        }
        if response_mime_type:
            generation_config = payload["generationConfig"]
            if isinstance(generation_config, dict):
                generation_config["responseMimeType"] = response_mime_type
        return payload

    def complete(
        self,
        messages: Iterable[LLMMessage],
        *,
        system_prompt: str,
        response_mime_type: str | None = None,
    ) -> tuple[str, LLMUsage]:
        payload = self._build_payload(
            messages,
            system_prompt=system_prompt,
            response_mime_type=response_mime_type,
        )
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self._base_url}/{self.model}:generateContent",
                params={"key": self.api_key},
                json=payload,
            )
            response.raise_for_status()
        data = response.json()
        text = self._extract_text(data)
        return text, self._extract_usage(data)

    def stream_complete(
        self,
        messages: Iterable[LLMMessage],
        *,
        system_prompt: str,
        on_chunk: Callable[[str], None] | None = None,
    ) -> tuple[str, LLMUsage]:
        payload = self._build_payload(messages, system_prompt=system_prompt)
        chunks: list[str] = []
        usage = LLMUsage()
        with httpx.Client(timeout=self.timeout) as client, client.stream(
            "POST",
            f"{self._base_url}/{self.model}:streamGenerateContent",
            params={"alt": "sse", "key": self.api_key},
            json=payload,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data = json.loads(line[6:])
                text = self._extract_text(data)
                if text:
                    chunks.append(text)
                    if on_chunk is not None:
                        on_chunk(text)
                usage = self._extract_usage(data) or usage
        return "".join(chunks), usage

    @staticmethod
    def _extract_text(data: dict[str, object]) -> str:
        candidates = data.get("candidates", [])
        if not isinstance(candidates, list) or not candidates:
            return ""
        first = candidates[0]
        if not isinstance(first, dict):
            return ""
        content = first.get("content", {})
        if not isinstance(content, dict):
            return ""
        parts = content.get("parts", [])
        if not isinstance(parts, list):
            return ""
        return "".join(
            part.get("text", "")
            for part in parts
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )

    @staticmethod
    def _extract_usage(data: dict[str, object]) -> LLMUsage:
        usage_data = data.get("usageMetadata", {})
        if not isinstance(usage_data, dict):
            return LLMUsage()
        prompt_tokens = int(usage_data.get("promptTokenCount", 0) or 0)
        completion_tokens = int(usage_data.get("candidatesTokenCount", 0) or 0)
        total_tokens = int(
            usage_data.get("totalTokenCount", prompt_tokens + completion_tokens) or 0
        )
        return LLMUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
