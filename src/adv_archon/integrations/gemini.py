from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

import httpx

from adv_archon.core.llm_types import LLMMessage, LLMUsage

# Separate timeouts: connection is fast, but reads during streaming can be slow
# for long reasoning responses.
_CONNECT_TIMEOUT = 15.0
_WRITE_TIMEOUT   = 30.0
_POOL_TIMEOUT    = 15.0
_READ_TIMEOUT_FACTOR = 1.0   # multiplied by configured timeout → per-read window


def _stream_timeout(total: float) -> httpx.Timeout:
    """
    For streaming: generous read timeout so idle gaps between chunks
    (while the model is reasoning) don't trigger premature disconnects.
    The 'read' timeout is per-chunk-read, not total response time.
    """
    return httpx.Timeout(
        connect=_CONNECT_TIMEOUT,
        read=total * _READ_TIMEOUT_FACTOR,
        write=_WRITE_TIMEOUT,
        pool=_POOL_TIMEOUT,
    )


def _sync_timeout(total: float) -> httpx.Timeout:
    return httpx.Timeout(
        connect=_CONNECT_TIMEOUT,
        read=total,
        write=_WRITE_TIMEOUT,
        pool=_POOL_TIMEOUT,
    )


@dataclass(slots=True)
class GeminiClient:
    api_key: str
    model: str
    temperature: float
    timeout: float = 300.0
    # Maximum number of retries on transient stream errors (idle timeout, 503)
    max_stream_retries: int = field(default=2)

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
                {"role": message.role, "parts": [{"text": message.content}]}
                for message in messages
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
        with httpx.Client(timeout=_sync_timeout(self.timeout)) as client:
            response = client.post(
                f"{self._base_url}/{self.model}:generateContent",
                params={"key": self.api_key},
                json=payload,
            )
            response.raise_for_status()
        data = response.json()
        return self._extract_text(data), self._extract_usage(data)

    def stream_complete(
        self,
        messages: Iterable[LLMMessage],
        *,
        system_prompt: str,
        on_chunk: Callable[[str], None] | None = None,
    ) -> tuple[str, LLMUsage]:
        """
        Stream a completion, retrying up to `max_stream_retries` times on
        transient errors (stream idle timeout, 503, read timeout).
        On retry, accumulated text is prepended so the caller still gets a
        complete response.
        """
        messages_list = list(messages)   # consume once, reuse on retries
        accumulated: list[str] = []
        last_usage = LLMUsage()
        last_error: Exception | None = None

        for attempt in range(self.max_stream_retries + 1):
            if attempt > 0:
                wait = 2.0 * attempt
                time.sleep(wait)

            try:
                chunks, usage = self._stream_once(
                    messages_list,
                    system_prompt=system_prompt,
                    on_chunk=on_chunk,
                    already_accumulated=accumulated,
                )
                accumulated.extend(chunks)
                last_usage = usage or last_usage
                return "".join(accumulated), last_usage

            except (_StreamIdleTimeout, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
                last_error = exc
                # Don't retry if we already got a substantial response
                if len("".join(accumulated)) > 200:
                    break
                continue

            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (429, 500, 503) and attempt < self.max_stream_retries:
                    last_error = exc
                    continue
                raise

        # All retries exhausted — return whatever we accumulated, or re-raise
        if accumulated:
            return "".join(accumulated), last_usage
        if last_error is not None:
            raise last_error
        return "", last_usage

    def _stream_once(
        self,
        messages: list[LLMMessage],
        *,
        system_prompt: str,
        on_chunk: Callable[[str], None] | None,
        already_accumulated: list[str],
    ) -> tuple[list[str], LLMUsage]:
        payload = self._build_payload(messages, system_prompt=system_prompt)
        chunks: list[str] = []
        usage = LLMUsage()

        with httpx.Client(timeout=_stream_timeout(self.timeout)) as client, client.stream(
            "POST",
            f"{self._base_url}/{self.model}:streamGenerateContent",
            params={"alt": "sse", "key": self.api_key},
            json=payload,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                raw = line[6:]
                # Gemini sometimes sends "[DONE]"
                if raw.strip() == "[DONE]":
                    break
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                # Check for server-side idle timeout error embedded in stream
                error = data.get("error", {})
                if isinstance(error, dict) and error:
                    msg = str(error.get("message", ""))
                    if "idle" in msg.lower() or "timeout" in msg.lower():
                        raise _StreamIdleTimeout(msg)
                    status = int(error.get("code", 0))
                    if status in (500, 503):
                        raise httpx.HTTPStatusError(
                            msg,
                            request=response.request,  # type: ignore[arg-type]
                            response=response,  # type: ignore[arg-type]
                        )

                text = self._extract_text(data)
                if text:
                    chunks.append(text)
                    if on_chunk is not None:
                        on_chunk(text)
                usage = self._extract_usage(data) or usage

        return chunks, usage

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


class _StreamIdleTimeout(Exception):
    """Raised when Gemini reports a stream idle timeout inside the SSE stream."""
