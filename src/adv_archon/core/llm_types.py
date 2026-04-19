from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class LLMMessage:
    role: str
    content: str


@dataclass(slots=True)
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


@dataclass(slots=True)
class LLMResponse:
    text: str
    usage: LLMUsage
    provider: str
    model: str
    redaction_applied: bool = False
    redaction_items: int = 0
