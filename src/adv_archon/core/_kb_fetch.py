"""Internal helper: fetch clean text from a URL for KB indexing."""

from __future__ import annotations

import ssl
import urllib.request
from contextlib import suppress
from html.parser import HTMLParser

_SKIP = {"script", "style", "noscript", "head", "nav", "footer", "header"}
_HEADERS = {
    "User-Agent": "AdvArchon-KB/1.0 (personal; local)",
    "Accept": "text/html,text/plain",
}


class _Strip(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._d = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in _SKIP:
            self._d += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP:
            self._d = max(0, self._d - 1)

    def handle_data(self, data: str) -> None:
        if self._d == 0 and data.strip():
            self._parts.append(data.strip())

    def text(self) -> str:
        return " ".join(self._parts)


def fetch_url_text(url: str, *, timeout: int = 15) -> str:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read(512_000)
            enc = resp.headers.get_content_charset() or "utf-8"
            html = raw.decode(enc, errors="replace")
    except Exception:
        return ""
    p = _Strip()
    with suppress(Exception):
        p.feed(html)
    return p.text()[:50_000]
