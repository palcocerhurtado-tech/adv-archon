from pathlib import Path
from types import SimpleNamespace

import adv_archon.main as main_module
from adv_archon.core.feedback_store import FeedbackStore


def test_desktop_main_launches_desktop_app(monkeypatch) -> None:
    config = SimpleNamespace(
        llm=SimpleNamespace(mode="local"),
        system_prompt_path=Path("/tmp/system.md"),
    )
    launched: dict[str, object] = {}

    monkeypatch.setattr(main_module, "load_app_config", lambda: config)
    monkeypatch.setattr(main_module, "load_system_prompt", lambda _path: "system prompt")
    monkeypatch.setattr(
        main_module,
        "LLMRouter",
        lambda _llm_config: (_ for _ in ()).throw(
            AssertionError("desktop_main must not build LLMRouter before showing UI")
        ),
    )

    def fake_launch_desktop_app(**kwargs):
        launched.update(kwargs)
        return 7

    monkeypatch.setattr(main_module, "launch_desktop_app", fake_launch_desktop_app)

    result = main_module.desktop_main()

    assert result == 7
    assert launched["config"] is config
    assert launched["llm"] is None
    assert launched["project_root"] == Path.cwd()
    assert launched["system_prompt"] == "system prompt"
    assert launched["incognito"] is False


def test_main_handles_desktop_bundle_prompt(monkeypatch, tmp_path: Path) -> None:
    config = SimpleNamespace(
        llm=SimpleNamespace(mode="local"),
        system_prompt_path=Path("/tmp/system.md"),
        ui=SimpleNamespace(show_tool_input=False),
    )
    bundle_calls: dict[str, object] = {}

    monkeypatch.setattr(main_module, "load_app_config", lambda **_kwargs: config)
    monkeypatch.setattr(main_module, "LLMRouter", lambda llm_config: ("router", llm_config))

    def fake_create_bundle(*, destination_dir: Path):
        bundle_calls["destination_dir"] = destination_dir
        return SimpleNamespace(
            app_path=destination_dir / "ADV ARCHON.app",
            launcher_path=(
                destination_dir
                / "ADV ARCHON.app"
                / "Contents"
                / "MacOS"
                / "adv-archon-desktop"
            ),
        )

    monkeypatch.setattr(main_module, "create_macos_app_bundle", fake_create_bundle)

    class FakeConsole:
        def __init__(self) -> None:
            self.messages: list[str] = []

        def print(self, message: str) -> None:
            self.messages.append(message)

    fake_console = FakeConsole()
    monkeypatch.setattr(main_module, "Console", lambda: fake_console)

    import sys

    monkeypatch.setattr(
        sys,
        "argv",
        ["adv-archon", "desktop-bundle", str(tmp_path)],
    )

    result = main_module.main()

    assert result == 0
    assert bundle_calls["destination_dir"] == tmp_path


def test_main_handles_export_training_data_prompt(monkeypatch, tmp_path: Path) -> None:
    config = SimpleNamespace(
        llm=SimpleNamespace(mode="local"),
        system_prompt_path=Path("/tmp/system.md"),
        ui=SimpleNamespace(show_tool_input=False),
        paths=SimpleNamespace(feedback_db=tmp_path / "feedback.db"),
    )
    store = FeedbackStore(config.paths.feedback_db)
    exp = SimpleNamespace(
        id="exp-1",
        title="Cambio de uso",
        address="Calle Mayor 1",
        municipality="Madrid",
        province="Madrid",
        cadastral_ref="7537903VK4873N0001OU",
        plan_path="/tmp/plano.pdf",
        notes="",
        case_type="cambio_uso_vivienda",
        site_context="{}",
    )
    store.add_example(
        exp,
        {"summary": "Apto con condiciones"},
        {"score": 90, "flags": [], "verdict": "APTO"},
    )
    output_path = tmp_path / "dataset.jsonl"

    monkeypatch.setattr(main_module, "load_app_config", lambda **_kwargs: config)
    monkeypatch.setattr(main_module, "LLMRouter", lambda llm_config: ("router", llm_config))

    import sys

    monkeypatch.setattr(
        sys,
        "argv",
        ["adv-archon", "export-training-data", str(output_path)],
    )

    result = main_module.main()

    assert result == 0
    assert "Apto con condiciones" in output_path.read_text(encoding="utf-8")


def test_main_handles_training_lab_status(monkeypatch, tmp_path: Path) -> None:
    config = SimpleNamespace(
        llm=SimpleNamespace(mode="local"),
        system_prompt_path=Path("/tmp/system.md"),
        ui=SimpleNamespace(show_tool_input=False),
        paths=SimpleNamespace(feedback_db=tmp_path / "feedback.db", root=tmp_path),
    )
    messages: list[str] = []

    monkeypatch.setattr(main_module, "load_app_config", lambda **_kwargs: config)
    monkeypatch.setattr(main_module, "LLMRouter", lambda llm_config: ("router", llm_config))

    class FakeRenderer:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def show_info(self, message: str) -> None:
            messages.append(message)

        def show_error(self, message: str) -> None:
            raise AssertionError(message)

    monkeypatch.setattr(main_module, "Renderer", FakeRenderer)

    import sys

    monkeypatch.setattr(sys, "argv", ["adv-archon", "training-lab", "status"])

    result = main_module.main()

    assert result == 0
    assert messages
    assert "Training Lab ADV ARCHON" in messages[0]
