from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adv_archon.core.knowledge import (
    KnowledgeIndexResult,
    KnowledgeStatus,
    KnowledgeStore,
)
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

    def knowledge_search(
        self,
        query: str,
        limit: int = 5,
        roots: list[str] | None = None,
        suffixes: list[str] | None = None,
    ) -> ToolResult:
        selected_roots = self._knowledge_roots(roots)
        records = self._store.search(
            query,
            limit=limit,
            roots=selected_roots,
            suffixes=suffixes,
        )
        status = self._store.status(selected_roots, limit_runs=1)
        return ToolResult(
            name="knowledge_search",
            payload={
                "query": query,
                "profile": self._active_profile(),
                "roots": selected_roots or [],
                "suffixes": list(suffixes or []),
                "status": _status_payload(status),
                "results": [
                    {
                        "path": record.path,
                        "title": record.title,
                        "excerpt": record.excerpt,
                        "root": record.root,
                        "relative_path": record.relative_path,
                        "content_type": record.content_type,
                        "suffix": record.suffix,
                        "file_size": record.file_size,
                        "modified_at": record.modified_at,
                        "indexed_at": record.indexed_at,
                        "score": record.score,
                        "matched_terms": list(record.matched_terms),
                    }
                    for record in records
                ],
            },
        )

    def vault_search(
        self,
        query: str,
        limit: int = 5,
        roots: list[str] | None = None,
    ) -> ToolResult:
        selected_roots = self._vault_roots(roots)
        records = self._store.search_vault(query, limit=limit, roots=selected_roots or None)
        status = self._store.status(selected_roots, limit_runs=1)
        return ToolResult(
            name="vault_search",
            payload={
                "query": query,
                "profile": self._active_profile(),
                "roots": selected_roots or [],
                "status": _status_payload(status),
                "results": [
                    {
                        "path": record.path,
                        "title": record.title,
                        "excerpt": record.excerpt,
                        "root": record.root,
                        "relative_path": record.relative_path,
                        "content_type": record.content_type,
                        "suffix": record.suffix,
                        "file_size": record.file_size,
                        "modified_at": record.modified_at,
                        "indexed_at": record.indexed_at,
                        "score": record.score,
                        "matched_terms": list(record.matched_terms),
                    }
                    for record in records
                ],
            },
        )

    def knowledge_index(
        self,
        paths: list[str] | None = None,
        batch_size: int | None = None,
        refresh: bool = True,
    ) -> ToolResult:
        result = self._run_once(paths=paths, batch_size=batch_size, refresh=refresh)
        return ToolResult(
            name="knowledge_index",
            payload=_index_payload(result),
        )

    def knowledge_discover(self, paths: list[str] | None = None) -> ToolResult:
        selected_paths = self._knowledge_roots(paths)
        result = self._store.discover_paths(selected_paths)
        status = self._store.status(selected_paths, limit_runs=1)
        return ToolResult(
            name="knowledge_discover",
            payload={
                "roots": result.roots,
                "run_id": result.run_id,
                "status": result.status,
                "scanned_files": result.scanned_files,
                "unchanged_files": result.unchanged_files,
                "pending_files": result.pending_files,
                "skipped_files": result.skipped_files,
                "failed_files": result.failed_files,
                "deleted_files": result.deleted_files,
                "index_status": _status_payload(status),
            },
        )

    def knowledge_ingest_batch(
        self,
        paths: list[str] | None = None,
        batch_size: int | None = None,
    ) -> ToolResult:
        selected_paths = self._knowledge_roots(paths)
        result = self._store.ingest_pending_batch(selected_paths, batch_size=batch_size)
        return ToolResult(
            name="knowledge_ingest_batch",
            payload=_index_payload(result),
        )

    def knowledge_status(
        self,
        paths: list[str] | None = None,
        limit_runs: int = 5,
    ) -> ToolResult:
        selected_paths = self._knowledge_roots(paths)
        status = self._store.status(selected_paths, limit_runs=limit_runs)
        return ToolResult(
            name="knowledge_status",
            payload=_status_payload(status, profile=self._active_profile()),
        )

    def _run_once(
        self,
        *,
        paths: list[str] | None,
        batch_size: int | None,
        refresh: bool,
    ) -> KnowledgeIndexResult:
        selected_paths = self._knowledge_roots(paths)
        if selected_paths is not None:
            return self._store.run_once(selected_paths, batch_size=batch_size, refresh=refresh)
        return self._store.run_once(batch_size=batch_size, refresh=refresh)

    def _knowledge_roots(self, paths: list[str] | None) -> list[str] | None:
        if paths:
            return paths
        if self._profile_manager:
            roots = list(self._profile_manager.knowledge_roots())
            if roots:
                return roots
        return None

    def _vault_roots(self, roots: list[str] | None) -> list[str] | None:
        if roots:
            return roots
        if self._profile_manager:
            selected = list(self._profile_manager.vault_roots())
            if selected:
                return selected
        return None

    def _active_profile(self) -> str | None:
        if self._profile_manager is None:
            return None
        return self._profile_manager.active_profile


def build_knowledge_tool_specs(tool: KnowledgeTools) -> list[dict[str, Any]]:
    return [
        {
            "name": "knowledge_search",
            "description": (
                "Search the local knowledge base with file metadata, lexical reranking, "
                "and semantic retrieval."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                    "roots": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "suffixes": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
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
                    "roots": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["query"],
            },
            "fn": tool.vault_search,
        },
        {
            "name": "knowledge_index",
            "description": (
                "Run one local indexing pass: optionally refresh discovery, then ingest "
                "a batch of pending files into the knowledge base."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "batch_size": {"type": "integer"},
                    "refresh": {"type": "boolean"},
                },
                "required": [],
            },
            "fn": tool.knowledge_index,
        },
        {
            "name": "knowledge_discover",
            "description": (
                "Refresh local file discovery only. Tracks pending, skipped, deleted, "
                "and changed files without doing heavy embedding work."
            ),
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
            "fn": tool.knowledge_discover,
        },
        {
            "name": "knowledge_ingest_batch",
            "description": (
                "Embed and index the next pending local knowledge batch without rescanning roots."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "batch_size": {"type": "integer"},
                },
                "required": [],
            },
            "fn": tool.knowledge_ingest_batch,
        },
        {
            "name": "knowledge_status",
            "description": (
                "Inspect local knowledge indexing status, backlog, and recent indexing runs."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "limit_runs": {"type": "integer"},
                },
                "required": [],
            },
            "fn": tool.knowledge_status,
        },
    ]


def _index_payload(result: KnowledgeIndexResult) -> dict[str, Any]:
    return {
        "run_id": result.run_id,
        "status": result.status,
        "roots": result.roots,
        "batch_size": result.batch_size,
        "scanned_files": result.scanned_files,
        "processed_files": result.processed_files,
        "indexed_files": result.indexed_files,
        "unchanged_files": result.unchanged_files,
        "skipped_files": result.skipped_files,
        "failed_files": result.failed_files,
        "deleted_files": result.deleted_files,
        "pending_files": result.pending_files,
    }


def _status_payload(
    status: KnowledgeStatus,
    *,
    profile: str | None = None,
) -> dict[str, Any]:
    return {
        "profile": profile,
        "roots": status.roots,
        "indexed_entries": status.indexed_entries,
        "discovered_files": status.discovered_files,
        "indexed_files": status.indexed_files,
        "pending_files": status.pending_files,
        "skipped_files": status.skipped_files,
        "error_files": status.error_files,
        "deleted_files": status.deleted_files,
        "last_run": _run_payload(status.last_run),
        "recent_runs": [_run_payload(run) for run in status.recent_runs],
    }


def _run_payload(run: Any) -> dict[str, Any] | None:
    if run is None:
        return None
    return {
        "run_id": run.run_id,
        "status": run.status,
        "roots": run.roots,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "batch_size": run.batch_size,
        "refresh": run.refresh,
        "scanned_files": run.scanned_files,
        "processed_files": run.processed_files,
        "indexed_files": run.indexed_files,
        "unchanged_files": run.unchanged_files,
        "skipped_files": run.skipped_files,
        "failed_files": run.failed_files,
        "deleted_files": run.deleted_files,
        "pending_files": run.pending_files,
        "message": run.message,
    }
