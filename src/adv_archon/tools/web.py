from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
import trafilatura
from duckduckgo_search import DDGS

USER_AGENT = "ADV-ARCHON/0.1 (+https://local-only)"


@dataclass(slots=True)
class ToolResult:
    name: str
    payload: dict[str, Any]


def web_search(query: str, n: int = 5) -> ToolResult:
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=n))
    normalized = [
        {
            "title": item.get("title", ""),
            "url": item.get("href", ""),
            "snippet": item.get("body", ""),
        }
        for item in results
    ]
    return ToolResult(name="web_search", payload={"query": query, "results": normalized})


def web_fetch(url: str) -> ToolResult:
    if not _allowed_by_robots(url):
        raise PermissionError(f"robots.txt disallows fetching: {url}")
    with httpx.Client(
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
        timeout=30.0,
    ) as client:
        response = client.get(url)
        response.raise_for_status()
    extracted = trafilatura.extract(response.text, include_links=True, include_tables=True)
    return ToolResult(
        name="web_fetch",
        payload={
            "url": url,
            "text": extracted or "",
        },
    )


def _allowed_by_robots(url: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.read()
    except OSError:
        return True
    return parser.can_fetch(USER_AGENT, url)

