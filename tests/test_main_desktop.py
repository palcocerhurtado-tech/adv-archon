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
    monkeypatch.setattr(main_module, "LLMRouter", lambda llm_config: ("router", llm_config))

    def fake_launch_desktop_app(**kwargs):
        launched.update(kwargs)
        return 7

    monkeypatch.setattr(main_module, "launch_desktop_app", fake_launch_desktop_app)

    result = main_module.desktop_main()

    assert result == 7
    assert launched["config"] is config
    assert launched["llm"] == ("router", config.llm)
    assert launched["project_root"] == Path.cwd()
    assert launched["system_prompt"] == "system prompt"
    assert launched["incognito"] is False
