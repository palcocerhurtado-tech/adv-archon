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
        category: str | None = None,
        importance: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        record = self._store.remember(
            fact,
            tags or [],
            source="agent",
            memory_type=memory_type,
            namespace=namespace,
            category=category,
            importance=importance,
            metadata=metadata,
        )
        return ToolResult(
            name="remember",
            payload={"record": _record_payload(record)},
        )

    def recall(
        self,
        query: str,
        limit: int = 5,
        memory_type: str | None = None,
        namespace: str | None = None,
        category: str | None = None,
        min_importance: int | None = None,
    ) -> ToolResult:
        records = self._store.recall(
            query,
            limit=limit,
            memory_type=memory_type,
            namespace=namespace,
            category=category,
            min_importance=min_importance,
        )
        return ToolResult(
            name="recall",
            payload={
                "query": query,
                "results": [_record_payload(record) for record in records],
            },
        )

    def list_memories(
        self,
        *,
        query: str | None = None,
        limit: int = 20,
        memory_type: str | None = None,
        namespace: str | None = None,
        category: str | None = None,
        min_importance: int | None = None,
    ) -> ToolResult:
        records = self._store.list_memories(
            query=query,
            limit=limit,
            memory_type=memory_type,
            namespace=namespace,
            category=category,
            min_importance=min_importance,
        )
        return ToolResult(
            name="memory_list",
            payload={
                "query": query,
                "results": [_record_payload(record) for record in records],
            },
        )

    def update_memory(
        self,
        memory_id: int,
        *,
        content: str | None = None,
        tags: list[str] | None = None,
        source: str | None = None,
        memory_type: str | None = None,
        namespace: str | None = None,
        category: str | None = None,
        importance: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        record = self._store.update_memory(
            memory_id,
            content=content,
            tags=tags,
            source=source,
            memory_type=memory_type,
            namespace=namespace,
            category=category,
            importance=importance,
            metadata=metadata,
        )
        return ToolResult(
            name="memory_update",
            payload={"record": _record_payload(record)},
        )

    def forget_memories(
        self,
        *,
        ids: list[int] | None = None,
        query: str | None = None,
        limit: int = 10,
    ) -> ToolResult:
        target_ids = list(ids or [])
        matched_records = []
        if query:
            matched_records = self._store.find_matches(query, limit=limit)
            target_ids.extend(record.id for record in matched_records)
        unique_ids = sorted(set(target_ids))
        deleted = self._store.forget_by_ids(unique_ids)
        return ToolResult(
            name="memory_forget",
            payload={
                "deleted": deleted,
                "ids": unique_ids,
                "matches": [_record_payload(record) for record in matched_records],
            },
        )


def _record_payload(record: Any) -> dict[str, Any]:
    return {
        "id": record.id,
        "content": record.content,
        "tags": record.tags,
        "score": record.score,
        "source": record.source,
        "memory_type": record.memory_type,
        "namespace": record.namespace,
        "category": record.category,
        "importance": record.importance,
        "metadata": record.metadata,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }
