from __future__ import annotations

from types import SimpleNamespace

from adv_archon.tools.vision import VisionTools, build_vision_tool_specs


def test_vision_tool_specs_are_local_first() -> None:
    tools = VisionTools(llm=None)

    specs = build_vision_tool_specs(tools)

    names = {spec["name"] for spec in specs}
    assert {
        "screenshot",
        "screen_describe",
        "screen_region_describe",
        "webcam_describe",
        "analyze_image_file",
    } <= names
    assert all("Gemini" not in spec["description"] for spec in specs)


def test_screen_describe_uses_local_ollama(monkeypatch) -> None:
    cfg = SimpleNamespace(
        vision_local_model="llava:latest",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_timeout_seconds=5,
        ollama_num_ctx=2048,
        ollama_keep_alive="-1",
    )
    tools = VisionTools(llm=SimpleNamespace(_config=cfg))
    monkeypatch.setattr(
        VisionTools,
        "_capture_screen",
        lambda self: ("ZmFrZQ==", "/tmp/fake.jpg", "image/jpeg"),
    )
    monkeypatch.setattr(
        VisionTools,
        "_ollama_vision",
        lambda self, image_b64, question, *, mime_type: (
            f"{image_b64}:{question}:{mime_type}"
        ),
    )

    result = tools.screen_describe("¿Qué ves?")

    assert result["ok"] is True
    assert result["provider"] == "ollama"
    assert result["model"] == "llava:latest"
    assert result["description"] == "ZmFrZQ==:¿Qué ves?:image/jpeg"


def test_vision_model_falls_back_to_default_when_text_model_configured() -> None:
    cfg = SimpleNamespace(
        ollama_model="qwen2.5:7b",
        ollama_base_url="http://127.0.0.1:11434",
    )

    assert VisionTools(llm=SimpleNamespace(_config=cfg))._vision_model() == "llava:latest"


def test_vision_model_uses_environment_override(monkeypatch) -> None:
    cfg = SimpleNamespace(ollama_model="qwen2.5:7b")
    monkeypatch.setenv("ADV_ARCHON_VISION_MODEL", "qwen2.5vl:7b")

    assert VisionTools(llm=SimpleNamespace(_config=cfg))._vision_model() == "qwen2.5vl:7b"


def test_analyze_image_file_reports_missing_path() -> None:
    result = VisionTools(llm=None).analyze_image_file("/tmp/no-existe-adv-archon.png")

    assert result["ok"] is False
    assert "Archivo no encontrado" in result["error"]
