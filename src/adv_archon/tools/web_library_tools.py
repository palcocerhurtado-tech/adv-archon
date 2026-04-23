from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adv_archon.core.web_library import WebLibraryStore
from adv_archon.tools.web import web_fetch, web_search


@dataclass(slots=True)
class ToolResult:
    name: str
    payload: dict[str, Any]


class WebLibraryTools:
    def __init__(self, store: WebLibraryStore) -> None:
        self._store = store

    def web_library_search(
        self,
        query: str,
        limit: int = 5,
        tags: list[str] | None = None,
        include_stale: bool = True,
    ) -> ToolResult:
        records = self._store.search(
            query,
            limit=limit,
            tags=tags,
            include_stale=include_stale,
        )
        return ToolResult(
            name="web_library_search",
            payload={
                "query": query,
                "results": [_record_payload(record) for record in records],
            },
        )

    def web_library_save_search(
        self,
        query: str,
        n: int = 5,
        tags: list[str] | None = None,
        freshness_ttl_hours: int = 72,
    ) -> ToolResult:
        search_result = web_search(query, n=n)
        ingest = self._store.ingest_search_results(
            query,
            search_result.payload["results"],
            tags=tags,
            freshness_ttl_hours=freshness_ttl_hours,
        )
        return ToolResult(
            name="web_library_save_search",
            payload={
                "query": query,
                "added": ingest.added,
                "updated": ingest.updated,
                "skipped": ingest.skipped,
                "records": [_record_payload(record) for record in ingest.records],
            },
        )

    def web_library_save_url(
        self,
        url: str,
        tags: list[str] | None = None,
        freshness_ttl_hours: int = 168,
    ) -> ToolResult:
        fetched = web_fetch(url)
        text = str(fetched.payload.get("text", "")).strip()
        record = self._store.upsert_entry(
            url=url,
            text=text,
            tags=tags,
            freshness_ttl_hours=freshness_ttl_hours,
        )
        return ToolResult(
            name="web_library_save_url",
            payload={
                "record": _record_payload(record),
            },
        )

    def web_library_refresh_stale(
        self,
        limit: int = 5,
    ) -> ToolResult:
        stale = self._store.search("", limit=limit * 4, include_stale=True)
        refreshed: list[dict[str, Any]] = []
        skipped = 0
        for record in stale:
            if record.freshness_state != "stale":
                continue
            try:
                fetched = web_fetch(record.url)
            except Exception:
                skipped += 1
                continue
            text = str(fetched.payload.get("text", "")).strip()
            refreshed_record = self._store.upsert_entry(
                url=record.url,
                title=record.title,
                text=text,
                tags=record.tags,
                source=record.source,
                source_type=record.source_type,
                freshness_ttl_hours=record.freshness_ttl_hours,
                metadata=record.metadata,
                published_at=record.published_at,
            )
            refreshed.append(_record_payload(refreshed_record))
            if len(refreshed) >= limit:
                break
        return ToolResult(
            name="web_library_refresh_stale",
            payload={
                "refreshed": refreshed,
                "skipped": skipped,
            },
        )


def build_web_library_tool_specs(tool: WebLibraryTools) -> list[dict[str, Any]]:
    return [
        {
            "name": "web_library_search",
            "description": "Search the local web knowledge library built from saved sources.",
            "schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "include_stale": {"type": "boolean"},
                },
                "required": ["query"],
            },
            "fn": tool.web_library_search,
        },
        {
            "name": "web_library_save_search",
            "description": "Run a web search and save the results into the local web library.",
            "schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "n": {"type": "integer"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "freshness_ttl_hours": {"type": "integer"},
                },
                "required": ["query"],
            },
            "fn": tool.web_library_save_search,
        },
        {
            "name": "web_library_save_url",
            "description": "Fetch one URL and save it into the local web library.",
            "schema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "freshness_ttl_hours": {"type": "integer"},
                },
                "required": ["url"],
            },
            "fn": tool.web_library_save_url,
        },
        {
            "name": "web_library_refresh_stale",
            "description": "Refresh stale sources in the local web library.",
            "schema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer"},
                },
                "required": [],
            },
            "fn": tool.web_library_refresh_stale,
        },
    ]


def _record_payload(record: Any) -> dict[str, Any]:
    return {
        "url": record.url,
        "canonical_url": record.canonical_url,
        "title": record.title,
        "source": record.source,
        "domain": record.domain,
        "source_type": record.source_type,
        "snippet": record.snippet,
        "tags": record.tags,
        "metadata": record.metadata,
        "freshness_ttl_hours": record.freshness_ttl_hours,
        "freshness_state": record.freshness_state,
        "age_hours": record.age_hours,
        "refresh_count": record.refresh_count,
        "updated_at": record.updated_at,
        "last_refreshed_at": record.last_refreshed_at,
        "stale_after": record.stale_after,
        "published_at": record.published_at,
        "score": record.score,
    }
