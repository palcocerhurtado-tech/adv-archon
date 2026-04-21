from __future__ import annotations

from pathlib import Path

import pytest

from adv_archon.tools.browser import BrowserTools


class FakeLocator:
    def __init__(self, page: FakePage, selector: str) -> None:
        self._page = page
        self._selector = selector
        self.first = self

    def click(self) -> None:
        self._page.clicked.append(self._selector)

    def fill(self, text: str) -> None:
        self._page.fills.append((self._selector, text))

    def press(self, key: str) -> None:
        self._page.presses.append((self._selector, key))

    def inner_text(self) -> str:
        if self._selector == "body":
            return self._page.body_text
        return self._page.selector_text.get(self._selector, "")


class FakePage:
    def __init__(self) -> None:
        self.url = "https://example.com"
        self.body_text = "Hola desde el navegador"
        self.selector_text = {"#result": "Texto extraido"}
        self.clicked: list[str] = []
        self.fills: list[tuple[str, str]] = []
        self.presses: list[tuple[str, str]] = []

    def goto(self, url: str, wait_until: str) -> None:
        self.url = url
        self.body_text = f"Contenido de {url}"
        assert wait_until == "domcontentloaded"

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)

    def title(self) -> str:
        return "Example"

    def screenshot(self, *, path: str, full_page: bool) -> None:
        Path(path).write_text("fake-image", encoding="utf-8")
        assert full_page is True


def test_browser_fill_and_extract_use_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts: list[str] = []
    page = FakePage()
    tool = BrowserTools(
        profile_dir=Path("/tmp/browser-profile"),
        confirm=lambda question: prompts.append(question) or True,
    )
    monkeypatch.setattr(tool, "_ensure_page", lambda: page)

    fill_result = tool.browser_fill("#search", "hola mundo", submit=True)
    extract_result = tool.browser_extract("#result")

    assert prompts and "Selector: #search" in prompts[0]
    assert page.fills == [("#search", "hola mundo")]
    assert page.presses == [("#search", "Enter")]
    assert fill_result.payload["title"] == "Example"
    assert extract_result.payload["text"] == "Texto extraido"


def test_browser_click_can_be_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    tool = BrowserTools(
        profile_dir=Path("/tmp/browser-profile"),
        confirm=lambda _question: False,
    )
    monkeypatch.setattr(tool, "_ensure_page", lambda: FakePage())

    with pytest.raises(PermissionError):
        tool.browser_click("#submit")
