from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from threading import Event
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
import trafilatura

from adv_archon.core.resilience import ConcurrencyPolicy, ResilientExecutor, RetryPolicy

try:
    from ddgs import DDGS as _DDGS
except ModuleNotFoundError:  # pragma: no cover - compatibilidad con instalaciones antiguas
    from duckduckgo_search import DDGS as _DDGS  # type: ignore[import-not-found,no-redef]

DDGS = _DDGS

USER_AGENT = "ADV-ARCHON/0.1 (+https://local-only)"
SHOP_PATH_HINTS = (
    "/collections/",
    "/collection",
    "/coleccion",
    "/p/",
    "/product/",
    "/products/",
    "/shop/",
    "/tienda/",
)
PRICE_TOKENS = ("€", "$", "£", "precio", "price", ".00", ",00")
PRICE_LINE_RE = re.compile(r"\d[\d.,]+\s*[€$£]|[€$£]\s*\d[\d.,]+")
COOKIE_BUTTON_LABELS = ("Aceptar", "Accept", "Aceptar todas", "Accept all")
PRICE_LINE_SKIP_TOKENS = (
    "envio",
    "envío",
    "free",
    "gastos",
    "gratuito",
    "shipping",
)
DEFAULT_SEARCH_TIMEOUT_SECONDS = 15.0
DEFAULT_FETCH_TIMEOUT_SECONDS = 15.0
DEFAULT_BROWSER_TIMEOUT_MS = 20_000


class ToolTimeoutError(TimeoutError):
    """Raised when a web tool exceeds its bounded execution window."""


class ToolCancelledError(RuntimeError):
    """Raised when the desktop UI cancels a running web tool."""


@dataclass(slots=True)
class ToolResult:
    name: str
    payload: dict[str, Any]


class WebTools:
    def __init__(
        self,
        *,
        retry_attempts: int = 3,
        retry_base_delay_seconds: float = 0.6,
        max_concurrency: int = 2,
        min_interval_seconds: float = 0.2,
    ) -> None:
        self._executor = ResilientExecutor(
            retry_policy=RetryPolicy(
                attempts=retry_attempts,
                base_delay_seconds=retry_base_delay_seconds,
            ),
            concurrency_policy=ConcurrencyPolicy(
                max_concurrency=max_concurrency,
                min_interval_seconds=min_interval_seconds,
            ),
        )

    def web_search(
        self,
        query: str,
        n: int = 5,
        cancel_event: Event | None = None,
    ) -> ToolResult:
        def _run() -> ToolResult:
            def _search() -> list[dict[str, Any]]:
                with DDGS() as ddgs:
                    return list(ddgs.text(query, max_results=n))

            results = _run_cancellable(
                _search,
                timeout_seconds=DEFAULT_SEARCH_TIMEOUT_SECONDS,
                cancel_event=cancel_event,
                timeout_message="La búsqueda tardó demasiado.",
            )
            normalized = [
                {
                    "title": item.get("title", ""),
                    "url": item.get("href", ""),
                    "snippet": item.get("body", ""),
                }
                for item in results
            ]
            return ToolResult(
                name="web_search",
                payload={"query": query, "results": normalized},
            )

        return self._executor.run(_run)

    def web_fetch(self, url: str, cancel_event: Event | None = None) -> ToolResult:
        def _run() -> ToolResult:
            _raise_if_cancelled(cancel_event)
            allowed = _run_cancellable(
                lambda: _allowed_by_robots(url),
                timeout_seconds=5.0,
                cancel_event=cancel_event,
                timeout_message="La comprobación de robots.txt tardó demasiado.",
            )
            if not allowed:
                raise PermissionError(f"robots.txt disallows fetching: {url}")

            extracted = ""
            try:
                extracted = _fetch_static_text(url, cancel_event=cancel_event)
            except Exception:
                extracted = ""

            _raise_if_cancelled(cancel_event)
            if _should_fallback_to_browser(url, extracted):
                browser_text = _fetch_browser_text(url, cancel_event=cancel_event)
                if browser_text:
                    extracted = browser_text

            return ToolResult(
                name="web_fetch",
                payload={
                    "url": url,
                    "text": extracted,
                },
            )

        return self._executor.run(_run)


_DEFAULT_WEB_TOOLS = WebTools()


def web_search(query: str, n: int = 5, cancel_event: Event | None = None) -> ToolResult:
    return _DEFAULT_WEB_TOOLS.web_search(query, n=n, cancel_event=cancel_event)


def web_fetch(url: str, cancel_event: Event | None = None) -> ToolResult:
    return _DEFAULT_WEB_TOOLS.web_fetch(url, cancel_event=cancel_event)


def _fetch_static_text(url: str, cancel_event: Event | None = None) -> str:
    _raise_if_cancelled(cancel_event)
    with httpx.Client(
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
        timeout=DEFAULT_FETCH_TIMEOUT_SECONDS,
    ) as client:
        response = client.get(url)
        response.raise_for_status()
    _raise_if_cancelled(cancel_event)
    return trafilatura.extract(
        response.text,
        include_links=True,
        include_tables=True,
    ) or ""


def _should_fallback_to_browser(url: str, extracted: str) -> bool:
    shop_page = any(hint in url for hint in SHOP_PATH_HINTS)
    has_price = any(token in extracted for token in PRICE_TOKENS)
    return len(extracted.strip()) < 200 or (shop_page and not has_price)


def _fetch_browser_text(url: str, cancel_event: Event | None = None) -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(user_agent=USER_AGENT)
            _raise_if_cancelled(cancel_event)
            page.goto(url, wait_until="networkidle", timeout=DEFAULT_BROWSER_TIMEOUT_MS)
            _accept_cookie_banner(page)
            _raise_if_cancelled(cancel_event)
            page_text = str(page.evaluate("() => document.body.innerText") or "")
            page_html = page.content()
        finally:
            browser.close()

    extracted = trafilatura.extract(
        page_html,
        include_links=True,
        include_tables=True,
    ) or ""
    price_hits = _extract_price_lines(page_text)
    if price_hits:
        extracted = "Precio: " + " | ".join(price_hits) + "\n\n" + extracted
    if not extracted:
        return page_text[:6000]
    return extracted


def _run_cancellable(
    fn: Any,
    *,
    timeout_seconds: float,
    cancel_event: Event | None,
    timeout_message: str,
) -> Any:
    deadline = time.monotonic() + timeout_seconds
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(fn)
    try:
        while True:
            _raise_if_cancelled(cancel_event)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                future.cancel()
                raise ToolTimeoutError(timeout_message)
            try:
                return future.result(timeout=min(0.2, remaining))
            except FutureTimeout:
                continue
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _raise_if_cancelled(cancel_event: Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise ToolCancelledError("Operación web cancelada por el usuario.")


def _accept_cookie_banner(page: Any) -> None:
    for label in COOKIE_BUTTON_LABELS:
        try:
            button = page.get_by_role("button", name=label)
            if button.is_visible(timeout=1500):
                button.click()
                page.wait_for_load_state("networkidle", timeout=5000)
                return
        except Exception:
            continue


def _extract_price_lines(page_text: str) -> list[str]:
    seen: list[str] = []
    for raw_line in page_text.splitlines():
        line = raw_line.strip()
        if not line or len(line) >= 60:
            continue
        lowered = line.lower()
        if any(token in lowered for token in PRICE_LINE_SKIP_TOKENS):
            continue
        if not PRICE_LINE_RE.search(line):
            continue
        if line not in seen:
            seen.append(line)
    return seen


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
