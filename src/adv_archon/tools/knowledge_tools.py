from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adv_archon.core.knowledge import KnowledgeStore


@dataclass(slots=True)
class ToolResult:
    name: str
    payload: dict[str, Any]


class KnowledgeTools:
    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    def knowledge_search(self, query: str, limit: int = 5) -> ToolResult:
        records = self._store.search(query, limit=limit)
        return ToolResult(
            name="knowledge_search",
            payload={
                "query": query,
                "results": [
                    {
                        "path": record.path,
                        "title": record.title,
                        "excerpt": record.excerpt,
                        "root": record.root,
                        "content_type": record.content_type,
                        "score": record.score,
                    }
                    for record in records
                ],
            },
        )

    def knowledge_index(self, paths: list[str] | None = None) -> ToolResult:
        result = (
            self._store.index_default_roots()
            if not paths
            else self._store.index_paths(paths)
        )
        return ToolResult(
            name="knowledge_index",
            payload={
                "scanned_files": result.scanned_files,
                "indexed_files": result.indexed_files,
                "skipped_files": result.skipped_files,
                "roots": result.roots,
            },
        )

