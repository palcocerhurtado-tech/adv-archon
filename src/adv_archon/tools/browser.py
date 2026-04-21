from __future__ import annotations

import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adv_archon.core.logging import AppLogger

ConfirmCallback = Callable[[str], bool]


@dataclass(slots=True)
class ToolResult:
    name: str
    payload: dict[str, Any]


class BrowserTools:
    def __init__(
        self,
        *,
        profile_dir: Path,
        enabled: bool = True,
        browser_name: str = "chromium",
        headless: bool = True,
        default_timeout_ms: int = 10000,
        confirm: ConfirmCallback | None = None,
        logger: AppLogger | None = None,
    ) -> None:
        self._profile_dir = profile_dir
        self._enabled = enabled
        self._browser_name = browser_name
        self._headless = headless
        self._default_timeout_ms = default_timeout_ms
        self._confirm = confirm
        self._logger = logger
        self._playwright: Any | None = None
        self._context: Any | None = None
        self._page: Any | None = None

    def browser_open(self, url: str) -> ToolResult:
        page = self._ensure_page()
        page.goto(url, wait_until="domcontentloaded")
        payload = self._snapshot(page)
        self._log("browser_open", url=url)
        return ToolResult(name="browser_open", payload=payload)

    def browser_click(self, selector: str) -> ToolResult:
        self._confirm_action(
            "Se va a hacer click en el navegador gestionado.\n"
            f"Selector: {selector}\n"
            "¿Confirmas?"
        )
        page = self._ensure_page()
        page.locator(selector).first.click()
        payload = self._snapshot(page)
        self._log("browser_click", selector=selector)
        return ToolResult(name="browser_click", payload=payload)

    def browser_fill(self, selector: str, text: str, submit: bool = False) -> ToolResult:
        preview = text if len(text) <= 120 else f"{text[:117]}..."
        action = "rellenar y enviar" if submit else "rellenar"
        self._confirm_action(
            "Se va a interactuar con el navegador gestionado.\n"
            f"Accion: {action}\n"
            f"Selector: {selector}\n"
            f"Texto: {preview}\n"
            "¿Confirmas?"
        )
        page = self._ensure_page()
        locator = page.locator(selector).first
        locator.fill(text)
        if submit:
            locator.press("Enter")
        payload = self._snapshot(page)
        self._log("browser_fill", selector=selector, chars=len(text), submit=submit)
        return ToolResult(name="browser_fill", payload=payload)

    def browser_extract(self, selector: str | None = None) -> ToolResult:
        page = self._ensure_page()
        if selector:
            text = page.locator(selector).first.inner_text()
        else:
            text = page.locator("body").inner_text()
        payload = self._snapshot(page)
        payload["text"] = text[:4000]
        self._log("browser_extract", selector=selector or "body")
        return ToolResult(name="browser_extract", payload=payload)

    def browser_screenshot(self, path: str | None = None) -> ToolResult:
        page = self._ensure_page()
        if path is None:
            screenshot_path = Path(tempfile.gettempdir()) / "adv-archon-browser.png"
        else:
            screenshot_path = Path(path).expanduser().resolve()
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_path), full_page=True)
        payload = self._snapshot(page)
        payload["path"] = str(screenshot_path)
        self._log("browser_screenshot", path=str(screenshot_path))
        return ToolResult(name="browser_screenshot", payload=payload)

    def browser_close(self) -> ToolResult:
        if self._page is not None:
            try:
                self._page.close()
            except Exception:
                self._log("browser_close_warning", target="page")
        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                self._log("browser_close_warning", target="context")
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                self._log("browser_close_warning", target="playwright")
        self._page = None
        self._context = None
        self._playwright = None
        self._log("browser_close")
        return ToolResult(name="browser_close", payload={"closed": True})

    def _ensure_page(self) -> Any:
        if not self._enabled:
            raise RuntimeError("La automatizacion de navegador esta desactivada en config.")
        try:
            from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "Falta `playwright`. Instala dependencias y ejecuta `playwright install chromium`."
            ) from exc

        if self._page is not None:
            return self._page

        self._profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        browser_type = getattr(self._playwright, self._browser_name, None)
        if browser_type is None:
            raise RuntimeError(f"Navegador no soportado: {self._browser_name}")
        try:
            self._context = browser_type.launch_persistent_context(
                user_data_dir=str(self._profile_dir),
                headless=self._headless,
            )
        except Exception as exc:
            message = str(exc)
            if "Executable doesn't exist" in message:
                raise RuntimeError(
                    "Falta instalar el navegador de Playwright. "
                    "Ejecuta `playwright install chromium`."
                ) from exc
            raise RuntimeError(
                f"No he podido arrancar el navegador automatizado: {message}"
            ) from exc
        self._context.set_default_timeout(self._default_timeout_ms)
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        return self._page

    @staticmethod
    def _snapshot(page: Any) -> dict[str, Any]:
        body_text = page.locator("body").inner_text()[:1200]
        return {
            "url": page.url,
            "title": page.title(),
            "body_excerpt": body_text,
        }

    def _confirm_action(self, question: str) -> None:
        if self._confirm is None:
            return
        if not self._confirm(question):
            raise PermissionError("Accion de navegador cancelada por el usuario.")

    def _log(self, event: str, **fields: object) -> None:
        if self._logger is not None:
            self._logger.log(event, **fields)


def build_browser_tool_specs(tool: BrowserTools) -> list[dict[str, Any]]:
    return [
        {
            "name": "browser_open",
            "description": "Open a page in the managed browser session.",
            "schema": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
            "fn": tool.browser_open,
        },
        {
            "name": "browser_click",
            "description": "Click an element in the current browser page.",
            "schema": {
                "type": "object",
                "properties": {"selector": {"type": "string"}},
                "required": ["selector"],
            },
            "fn": tool.browser_click,
        },
        {
            "name": "browser_fill",
            "description": "Fill an input in the current browser page.",
            "schema": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string"},
                    "text": {"type": "string"},
                    "submit": {"type": "boolean"},
                },
                "required": ["selector", "text"],
            },
            "fn": tool.browser_fill,
        },
        {
            "name": "browser_extract",
            "description": "Extract visible text from the current page or one selector.",
            "schema": {
                "type": "object",
                "properties": {"selector": {"type": "string"}},
                "required": [],
            },
            "fn": tool.browser_extract,
        },
        {
            "name": "browser_screenshot",
            "description": "Save a screenshot of the current browser page.",
            "schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": [],
            },
            "fn": tool.browser_screenshot,
        },
        {
            "name": "browser_close",
            "description": "Close the managed browser session.",
            "schema": {"type": "object", "properties": {}, "required": []},
            "fn": tool.browser_close,
        },
    ]
