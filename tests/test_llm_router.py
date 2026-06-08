from __future__ import annotations

from adv_archon.core.config import LLMConfig
from adv_archon.core.llm import LLMRouter
from adv_archon.core.llm_types import LLMMessage, LLMUsage


class FakeProvider:
    def __init__(self, *, model: str) -> None:
        self.model = model

    def complete(self, *_args, **_kwargs):
        return "ok", LLMUsage()

    def stream_complete(self, *_args, **_kwargs):
        return "ok", LLMUsage()


def test_llm_router_uses_planner_local_model(monkeypatch) -> None:
    config = LLMConfig(
        mode="local",
        ollama_model="llama-general",
        planner_local_model="llama-planner",
    )
    router = LLMRouter(config)
    captured: dict[str, str] = {}

    def fake_provider(self, mode: str, *, model: str):
        captured["mode"] = mode
        captured["model"] = model
        return FakeProvider(model=model)

    monkeypatch.setattr(LLMRouter, "_provider", fake_provider, raising=False)

    response = router.complete(
        [LLMMessage(role="user", content="hola")],
        system_prompt="system",
        task="planner",
    )

    assert response.model == "llama-planner"
    assert captured["mode"] == "local"
    assert captured["model"] == "llama-planner"


def test_llm_router_prefers_local_for_document_tasks(monkeypatch) -> None:
    config = LLMConfig(
        mode="cloud",
        gemini_api_key="test-key",
        gemini_model="gemini-general",
        ollama_model="llama-general",
        document_local_model="llama-docs",
    )
    router = LLMRouter(config)
    captured: dict[str, str] = {}

    def fake_provider(self, mode: str, *, model: str):
        captured["mode"] = mode
        captured["model"] = model
        return FakeProvider(model=model)

    monkeypatch.setattr(LLMRouter, "_provider", fake_provider, raising=False)

    response = router.stream_complete(
        [LLMMessage(role="user", content="resume este PDF")],
        system_prompt="system",
        task="documents",
    )

    assert response.provider == "ollama"
    assert captured["mode"] == "local"
    assert captured["model"] == "llama-docs"
