from __future__ import annotations

import plistlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from adv_archon.core.logging import AppLogger
from adv_archon.core.web_library import WebLibraryStore
from adv_archon.tools.web import web_fetch, web_search


@dataclass(slots=True)
class ResearchCycleResult:
    queries: list[str]
    saved_results: int
    refreshed_urls: int
    failed_urls: int


def run_research_cycle(
    *,
    store: WebLibraryStore,
    queries: list[str],
    search_results_per_query: int = 5,
    fetch_top_results: int = 2,
    logger: AppLogger | None = None,
) -> ResearchCycleResult:
    saved_results = 0
    refreshed_urls = 0
    failed_urls = 0
    clean_queries = [query.strip() for query in queries if query.strip()]

    for query in clean_queries:
        search_result = web_search(query, n=search_results_per_query)
        ingest = store.ingest_search_results(
            query,
            cast(list[dict[str, object]], search_result.payload["results"]),
            tags=["web-cycle", *query.lower().split()[:4]],
            freshness_ttl_hours=72,
        )
        saved_results += ingest.added + ingest.updated

        for item in search_result.payload["results"][:fetch_top_results]:
            url = str(item.get("url", "")).strip()
            if not url:
                continue
            try:
                fetched = web_fetch(url)
            except Exception:
                failed_urls += 1
                continue
            text = str(fetched.payload.get("text", "")).strip()
            store.upsert_entry(
                url=url,
                title=str(item.get("title", "")).strip() or None,
                text=text,
                snippet=str(item.get("snippet", "")).strip() or None,
                tags=["web-cycle", *query.lower().split()[:4]],
                source="duckduckgo",
                source_type="page",
                freshness_ttl_hours=72,
                metadata={"query": query},
            )
            refreshed_urls += 1

    if logger is not None:
        logger.log(
            "research_cycle_ran",
            queries=clean_queries,
            saved_results=saved_results,
            refreshed_urls=refreshed_urls,
            failed_urls=failed_urls,
        )

    return ResearchCycleResult(
        queries=clean_queries,
        saved_results=saved_results,
        refreshed_urls=refreshed_urls,
        failed_urls=failed_urls,
    )


def install_research_launch_agent(
    *,
    adv_command: str,
    queries: list[str],
    interval_minutes: int = 180,
) -> Path:
    launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
    launch_agents_dir.mkdir(parents=True, exist_ok=True)
    plist_path = launch_agents_dir / "com.adv-archon.research.plist"
    plist_path.write_bytes(
        plistlib.dumps(
            {
                "Label": "com.adv-archon.research",
                "ProgramArguments": [adv_command, "research", "run-once", *queries],
                "StartInterval": interval_minutes * 60,
                "RunAtLoad": True,
            }
        )
    )
    subprocess.run(["launchctl", "unload", str(plist_path)], check=False, capture_output=True)
    completed = subprocess.run(
        ["launchctl", "load", str(plist_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "No he podido cargar el launch agent.")
    return plist_path
