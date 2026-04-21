from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adv_archon.core.knowledge import KnowledgeStore
from adv_archon.core.profiles import ProfileManager


@dataclass(slots=True)
class ToolResult:
    name: str
    payload: dict[str, Any]


class KnowledgeTools:
    def __init__(
        self,
        store: KnowledgeStore,
        *,
        profile_manager: ProfileManager | None = None,
    ) -> None:
        self._store = store
        self._profile_manager = profile_manager

    def knowledge_search(self, query: str, limit: int = 5) -> ToolResult:
        roots = self._profile_manager.knowledge_roots() if self._profile_manager else ()
        records = self._store.search(query, limit=limit, roots=roots or None)
        return ToolResult(
            name="knowledge_search",
            payload={
                "query": query,
                "profile": self._profile_manager.active_profile if self._profile_manager else None,
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

    def vault_search(self, query: str, limit: int = 5) -> ToolResult:
        roots = self._profile_manager.vault_roots() if self._profile_manager else ()
        records = self._store.search_vault(query, limit=limit, roots=roots or None)
        return ToolResult(
            name="vault_search",
            payload={
                "query": query,
                "profile": self._profile_manager.active_profile if self._profile_manager else None,
                "roots": list(roots),
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
        if paths:
            result = self._store.index_paths(paths)
        elif self._profile_manager and self._profile_manager.knowledge_roots():
            result = self._store.index_paths(self._profile_manager.knowledge_roots())
        else:
            result = self._store.index_default_roots()
        return ToolResult(
            name="knowledge_index",
            payload={
                "scanned_files": result.scanned_files,
                "indexed_files": result.indexed_files,
                "skipped_files": result.skipped_files,
                "roots": result.roots,
            },
        )


def build_knowledge_tool_specs(tool: KnowledgeTools) -> list[dict[str, Any]]:
    return [
        {
            "name": "knowledge_search",
            "description": (
                "Search the local read-only knowledge base for relevant files and excerpts."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
            },
            "fn": tool.knowledge_search,
        },
        {
            "name": "vault_search",
            "description": "Search configured Markdown or Obsidian vaults for relevant notes.",
            "schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
            },
            "fn": tool.vault_search,
        },
        {
            "name": "knowledge_index",
            "description": "Index local knowledge roots in read-only mode.",
            "schema": {
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                    }
                },
                "required": [],
            },
            "fn": tool.knowledge_index,
        },
    ]
