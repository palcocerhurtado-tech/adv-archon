from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adv_archon.core.memory import MemoryStore


@dataclass(slots=True)
class ToolResult:
    name: str
    payload: dict[str, Any]


class MemoryTools:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def remember(self, fact: str, tags: list[str] | None = None) -> ToolResult:
        record = self._store.remember(fact, tags or [], source="agent")
        return ToolResult(
            name="remember",
            payload={
                "id": record.id,
                "content": record.content,
                "tags": record.tags,
                "source": record.source,
            },
        )

    def recall(self, query: str, limit: int = 5) -> ToolResult:
        records = self._store.recall(query, limit=limit)
        return ToolResult(
            name="recall",
            payload={
                "query": query,
                "results": [
                    {
                        "id": record.id,
                        "content": record.content,
                        "tags": record.tags,
                        "score": record.score,
                    }
                    for record in records
                ],
            },
        )

