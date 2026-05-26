from __future__ import annotations

from dataclasses import dataclass

CHARS_PER_TOKEN = 3.8
TRUNCATION_MARKER = "\n[...truncado por límite de contexto]"


@dataclass(frozen=True, slots=True)
class TokenSlot:
    name: str
    text: str
    priority: int


class TokenBudget:
    """Lightweight token budget manager for local LLM calls.

    Inspired by the context-window constraints described in chapter 2 of
    LLMs-from-scratch: the context is finite, so ADV ARCHON must choose what
    enters instead of letting Ollama truncate silently.
    """

    def __init__(self, max_tokens: int, reserved_output: int = 512) -> None:
        self.max_tokens = max(1, int(max_tokens))
        self.reserved = max(0, int(reserved_output))
        self._slots: list[TokenSlot] = []
        self._last_used_tokens = 0

    def estimate(self, text: str) -> int:
        return max(1, int(len(text) / CHARS_PER_TOKEN))

    def add(self, name: str, text: str, priority: int = 5) -> None:
        self._slots.append(TokenSlot(name=name, text=text or "", priority=int(priority)))

    def build(self) -> dict[str, str]:
        available = max(1, self.max_tokens - self.reserved)
        result: dict[str, str] = {}
        used = 0
        for slot in sorted(self._slots, key=lambda item: item.priority, reverse=True):
            cost = self.estimate(slot.text)
            if used + cost <= available:
                result[slot.name] = slot.text
                used += cost
                continue
            remaining = available - used
            if remaining >= 200:
                chars = int(remaining * CHARS_PER_TOKEN)
                result[slot.name] = slot.text[:chars] + TRUNCATION_MARKER
                used = available
            break
        self._last_used_tokens = used
        return result

    @property
    def utilization(self) -> float:
        available = max(1, self.max_tokens - self.reserved)
        total = sum(self.estimate(slot.text) for slot in self._slots)
        return total / available

    @property
    def last_used_tokens(self) -> int:
        return self._last_used_tokens


__all__ = ["CHARS_PER_TOKEN", "TRUNCATION_MARKER", "TokenBudget", "TokenSlot"]
