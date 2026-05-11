"""Skill: Research assistant.

Fetches web pages and synthesizes information using the LLM.
Uses only stdlib urllib — no external HTTP deps.
"""

from __future__ import annotations

import ssl
import urllib.request
from contextlib import suppress
from html.parser import HTMLParser
from typing import Any

from adv_archon.skills.base import Skill, SkillResult
from adv_archon.skills.registry import registry

_HEADERS = {
    "User-Agent": "AdvArchon-Research/1.0 (academic)",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml",
}
_SKIP_TAGS = {"script", "style", "noscript", "head", "nav", "footer"}


class _StripHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip = max(0, self._skip - 1)

    def handle_data(self, data: str) -> None:
        if self._skip == 0 and data.strip():
            self._parts.append(data.strip())

    def text(self) -> str:
        return " ".join(self._parts)


def _fetch(url: str, timeout: int = 12) -> str:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read(256_000)
            enc = resp.headers.get_content_charset() or "utf-8"
            html = raw.decode(enc, errors="replace")
    except Exception as exc:
        return f"[Error fetching {url}: {exc}]"

    parser = _StripHTML()
    with suppress(Exception):
        parser.feed(html)
    return parser.text()[:8000]


class ResearchSkill(Skill):
    name = "research"
    description = (
        "Investiga un tema buscando información en URLs proporcionadas y sintetiza "
        "los hallazgos en un informe estructurado."
    )
    args_schema = {
        "topic": {
            "type": "string",
            "description": "Tema o pregunta de investigación.",
        },
        "urls": {
            "type": "string",
            "description": "URLs separadas por comas para consultar (opcional).",
        },
    }

    def __init__(self, llm: Any | None = None) -> None:
        self._llm = llm

    def run(self, *, topic: str, urls: str = "", **_: Any) -> SkillResult:  # type: ignore[override]
        url_list = [u.strip() for u in urls.split(",") if u.strip()]

        fetched: list[str] = []
        for url in url_list[:4]:  # limit to 4 sources
            content = _fetch(url)
            fetched.append(f"[Fuente: {url}]\n{content[:2000]}")

        sources_text = "\n\n---\n\n".join(fetched) if fetched else "(Sin fuentes externas)"

        if self._llm:
            from adv_archon.core.llm_types import LLMMessage

            prompt = (
                f"Investiga el siguiente tema y sintetiza la información:\n\n"
                f"Tema: {topic}\n\n"
                f"Fuentes:\n{sources_text}\n\n"
                "Genera un informe de investigación con: resumen ejecutivo, "
                "hallazgos principales, y conclusiones."
            )
            resp = self._llm.complete(
                [LLMMessage(role="user", content=prompt)],
                system_prompt="Eres un investigador experto. Responde en español con rigor.",
                task="reasoning",
            )
            output = resp.text
        else:
            output = (
                f"Investigación sobre: {topic}\n\n"
                f"Fuentes consultadas: {len(url_list)}\n\n"
                f"{sources_text[:3000]}"
            )

        return SkillResult(
            success=True,
            output=output,
            artifacts={"topic": topic, "sources": url_list},
        )


registry.register(ResearchSkill())
