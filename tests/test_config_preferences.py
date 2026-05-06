from __future__ import annotations

from adv_archon.core.config import save_ollama_model_preference


def test_save_ollama_model_preference_creates_llm_section(tmp_path) -> None:
    config_file = tmp_path / "config.toml"

    save_ollama_model_preference(config_file, "qwen2.5:7b")

    assert '[llm]\nollama_model = "qwen2.5:7b"' in config_file.read_text()


def test_save_ollama_model_preference_updates_existing_key(tmp_path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[llm]\nmode = "local"\nollama_model = "llama3.1:8b"\n\n[ui]\n',
        encoding="utf-8",
    )

    save_ollama_model_preference(config_file, "mistral:7b")

    text = config_file.read_text(encoding="utf-8")
    assert 'ollama_model = "mistral:7b"' in text
    assert '[ui]' in text
