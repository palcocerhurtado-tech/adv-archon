from __future__ import annotations

from adv_archon.core.config import KnowledgeConfig, LLMConfig, load_app_config


def test_llm_defaults_use_fast_local_routing() -> None:
    cfg = LLMConfig()

    assert cfg.mode == "local"
    assert cfg.ollama_model == "llama3.2:3b"
    assert cfg.fast_local_model == "llama3.2:3b"
    assert cfg.planner_local_model == "llama3.2:3b"
    assert cfg.document_local_model == "llama3.1:8b"
    assert cfg.coding_local_model == "llama3.1:8b"
    assert cfg.reasoning_local_model == "llama3.1:8b"


def test_knowledge_defaults_are_opt_in() -> None:
    cfg = KnowledgeConfig()

    assert cfg.default_roots == ()
    assert cfg.auto_index_on_search is False


def test_load_app_config_safe_defaults(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADV_ARCHON_HOME", str(tmp_path))
    monkeypatch.delenv("ADV_ARCHON_DEFAULT_MODE", raising=False)
    monkeypatch.delenv("ADV_ARCHON_DEFAULT_OLLAMA_MODEL", raising=False)

    cfg = load_app_config()

    assert cfg.llm.mode == "local"
    assert cfg.llm.ollama_model == "llama3.2:3b"
    assert cfg.llm.temperature == 0.0
    assert cfg.llm.planner_local_model == "llama3.2:3b"
    assert cfg.llm.reasoning_local_model == "llama3.1:8b"
    assert cfg.knowledge.default_roots == ()
    assert cfg.knowledge.auto_index_on_search is False
