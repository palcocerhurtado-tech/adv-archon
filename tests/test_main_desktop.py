from pathlib import Path
from types import SimpleNamespace

import adv_archon.main as main_module


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
