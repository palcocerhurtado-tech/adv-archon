from __future__ import annotations

from types import SimpleNamespace


def _config() -> SimpleNamespace:
    return SimpleNamespace(
        llm=SimpleNamespace(
            ollama_base_url="http://localhost:11434",
            ollama_model="qwen2.5:7b",
            vision_local_model="llava:latest",
        )
    )


def test_run_qa_checks_returns_expected_items(monkeypatch) -> None:
    from adv_archon.desktop import qa

    fake = qa.QAItem("x", "X", True, "OK")
    monkeypatch.setattr(qa, "_check_microphone_input", lambda: fake)
    monkeypatch.setattr(qa, "_check_ollama_health", lambda _base_url: fake)
    monkeypatch.setattr(qa, "_check_local_model", lambda _base_url, _model: fake)
    monkeypatch.setattr(qa, "_check_vision_model", lambda _base_url, _model: fake)
    monkeypatch.setattr(qa, "_check_screen_capture_permission", lambda: fake)

    assert len(qa.run_qa_checks(_config())) == 5


def test_model_check_matches_prefix(monkeypatch) -> None:
    from adv_archon.desktop import qa

    monkeypatch.setattr(
        qa,
        "_ollama_tags",
        lambda _base_url: {"models": [{"name": "qwen2.5:7b-instruct"}]},
    )

    item = qa._check_local_model("http://localhost:11434", "qwen2.5:7b")

    assert item.ok is True
    assert "qwen2.5" in item.detalle


def test_microphone_check_reports_missing_sounddevice(monkeypatch) -> None:
    from adv_archon.desktop import qa

    def fake_import_module(name: str):
        if name == "sounddevice":
            raise ImportError("missing")
        return original_import_module(name)

    original_import_module = qa.importlib.import_module
    monkeypatch.setattr(qa.importlib, "import_module", fake_import_module)

    item = qa._check_microphone_input()

    assert item.ok is False
    assert "Micrófono" in item.nombre


def test_screen_capture_non_macos_is_ok(monkeypatch) -> None:
    from adv_archon.desktop import qa

    monkeypatch.setattr(qa.sys, "platform", "linux")

    item = qa._check_screen_capture_permission()

    assert item.ok is True
