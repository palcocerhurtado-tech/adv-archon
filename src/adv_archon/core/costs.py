from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import NamedTuple

from adv_archon.core.llm_types import LLMResponse


@dataclass(slots=True)
class UsageEvent:
    phase: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    timestamp: str
    redaction_applied: bool
    redaction_items: int


@dataclass(slots=True)
class UsageBreakdown:
    provider: str
    model: str
    phase: str
    calls: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float


@dataclass(slots=True)
class UsageSummary:
    total_calls: int
    planner_calls: int
    assistant_calls: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    redacted_calls: int
    redacted_items: int
    breakdowns: list[UsageBreakdown]


class _BreakdownKey(NamedTuple):
    provider: str
    model: str
    phase: str


class UsageLedger:
    def __init__(self) -> None:
        self._events: list[UsageEvent] = []

    def record(self, phase: str, response: LLMResponse) -> UsageEvent:
        event = UsageEvent(
            phase=phase,
            provider=response.provider,
            model=response.model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            estimated_cost_usd=response.usage.estimated_cost_usd,
            timestamp=datetime.now(UTC).isoformat(),
            redaction_applied=response.redaction_applied,
            redaction_items=response.redaction_items,
        )
        self._events.append(event)
        return event

    def summary(self) -> UsageSummary:
        planner_calls = len([event for event in self._events if event.phase == "planner"])
        assistant_calls = len([event for event in self._events if event.phase == "assistant"])
        breakdown_map: dict[_BreakdownKey, UsageBreakdown] = {}
        for event in self._events:
            key = _BreakdownKey(event.provider, event.model, event.phase)
            current = breakdown_map.get(key)
            if current is None:
                breakdown_map[key] = UsageBreakdown(
                    provider=event.provider,
                    model=event.model,
                    phase=event.phase,
                    calls=1,
                    prompt_tokens=event.prompt_tokens,
                    completion_tokens=event.completion_tokens,
                    total_tokens=event.total_tokens,
                    estimated_cost_usd=event.estimated_cost_usd,
                )
            else:
                current.calls += 1
                current.prompt_tokens += event.prompt_tokens
                current.completion_tokens += event.completion_tokens
                current.total_tokens += event.total_tokens
                current.estimated_cost_usd = round(
                    current.estimated_cost_usd + event.estimated_cost_usd,
                    6,
                )
        return UsageSummary(
            total_calls=len(self._events),
            planner_calls=planner_calls,
            assistant_calls=assistant_calls,
            prompt_tokens=sum(event.prompt_tokens for event in self._events),
            completion_tokens=sum(event.completion_tokens for event in self._events),
            total_tokens=sum(event.total_tokens for event in self._events),
            estimated_cost_usd=round(
                sum(event.estimated_cost_usd for event in self._events),
                6,
            ),
            redacted_calls=len([event for event in self._events if event.redaction_applied]),
            redacted_items=sum(event.redaction_items for event in self._events),
            breakdowns=sorted(
                breakdown_map.values(),
                key=lambda item: (item.provider, item.model, item.phase),
            ),
        )

    def recent_events(self, limit: int = 10) -> list[UsageEvent]:
        return self._events[-limit:]
