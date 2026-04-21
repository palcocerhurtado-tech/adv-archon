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

    def remember(
        self,
        fact: str,
        tags: list[str] | None = None,
        memory_type: str = "fact",
        namespace: str = "general",
    ) -> ToolResult:
        record = self._store.remember(
            fact,
            tags or [],
            source="agent",
            memory_type=memory_type,
            namespace=namespace,
        )
        return ToolResult(
            name="remember",
            payload={
                "id": record.id,
                "content": record.content,
                "tags": record.tags,
                "source": record.source,
                "memory_type": record.memory_type,
                "namespace": record.namespace,
            },
        )

    def recall(
        self,
        query: str,
        limit: int = 5,
        memory_type: str | None = None,
        namespace: str | None = None,
    ) -> ToolResult:
        records = self._store.recall(
            query,
            limit=limit,
            memory_type=memory_type,
            namespace=namespace,
        )
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
                        "memory_type": record.memory_type,
                        "namespace": record.namespace,
                    }
                    for record in records
                ],
            },
        )
