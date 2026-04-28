from pathlib import Path

from adv_archon.ui.commands import CommandServices, handle_command
from adv_archon.voice.stt import TranscriptionResult


class FakeRenderer:
    def __init__(self) -> None:
        self.infos: list[str] = []
        self.errors: list[str] = []

    def show_info(self, message: str) -> None:
        self.infos.append(message)

    def show_error(self, message: str) -> None:
        self.errors.append(message)

    def show_help(self) -> None:
        self.infos.append("help")


class FakeLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def log(self, event: str, **fields: object) -> None:
        self.events.append((event, fields))

    def recent(self, limit: int = 10) -> list[object]:
        return []


class FakeLLM:
    def __init__(self) -> None:
        self.mode = "local"

    def set_mode(self, mode: str) -> None:
        self.mode = mode


class FakeUsageLedger:
    def summary(self) -> object:
        raise AssertionError("Not used in this test")

    def recent_events(self, limit: int = 5) -> list[object]:
        raise AssertionError("Not used in this test")


class FakeMemory:
    pass


class FakeTaskStore:
    pass


class FakePersonalTools:
    def notes_create(self, title: str, body: str, folder: str | None = None) -> object:
        from adv_archon.tools.personal import ToolResult

        return ToolResult(
            name="notes_create",
            payload={"title": title, "body": body, "folder": folder},
        )


class FakeGoogleWorkspaceTools:
    pass


class FakeKnowledgeStore:
    pass


class FakeKnowledgeTools:
    def vault_search(self, query: str, limit: int = 5) -> object:
        from adv_archon.tools.knowledge_tools import ToolResult

        return ToolResult(
            name="vault_search",
            payload={
                "profile": "work",
                "results": [
                    {
                        "title": "acme.md",
                        "path": "/tmp/acme.md",
                        "excerpt": f"resultado para {query}",
                    }
                ],
            },
        )


class FakeProfile:
    def __init__(self, name: str) -> None:
        self.name = name
        self.description = f"Perfil {name}"
        self.knowledge_roots = ("~/Documents",)
        self.vault_roots = ("~/Vault",)


class FakeProfileManager:
    def __init__(self) -> None:
        self.active_profile = "general"

    def describe(self) -> FakeProfile:
        return FakeProfile(self.active_profile)

    def set_active_profile(self, profile_name: str) -> str:
        self.active_profile = profile_name
        return profile_name


class FakeAutoMode:
    def status(self) -> str:
        return "off"


class FakeShellTool:
    pass


class FakePythonTool:
    pass


class FakeTTS:
    def __init__(self) -> None:
        self.enabled = False

    def enable(self) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False

    def describe(self) -> str:
        return "on" if self.enabled else "off"


class FakeSTT:
    def describe(self) -> str:
        return "modelo=small | idioma=es | wake-word=off"

    def listen_once(self) -> TranscriptionResult:
        return TranscriptionResult(text="abre el README", language="es", duration_seconds=1.5)


class FakeFileTools:
    def read_file(self, path: str) -> object:
        from adv_archon.tools.files import ToolResult

        return ToolResult(
            name="read_file",
            payload={"path": path, "content": "contenido"},
        )


class FakeWebTools:
    def web_search(self, query: str) -> object:
        from adv_archon.tools.web import ToolResult

        return ToolResult(
            name="web_search",
            payload={
                "results": [
                    {
                        "title": "Resultado",
                        "url": "https://example.com",
                        "snippet": f"resultado para {query}",
                    }
                ]
            },
        )


def build_services() -> CommandServices:
    return CommandServices(
        llm=FakeLLM(),
        renderer=FakeRenderer(),
        memory=FakeMemory(),
        task_store=FakeTaskStore(),
        personal_tools=FakePersonalTools(),
        google_workspace_tools=FakeGoogleWorkspaceTools(),
        knowledge_store=FakeKnowledgeStore(),
        usage_ledger=FakeUsageLedger(),
        logger=FakeLogger(),
        context_provider=lambda: None,
        project_root=Path("/tmp/project"),
        logs_dir=Path("/tmp/logs"),
        confirm=lambda prompt: True,
        recall_limit=5,
        incognito=False,
        auto_mode=FakeAutoMode(),
        shell_tool=FakeShellTool(),
        python_tool=FakePythonTool(),
        knowledge_tools=FakeKnowledgeTools(),
        file_tools=FakeFileTools(),
        web_tools=FakeWebTools(),
        profile_manager=FakeProfileManager(),
        on_profile_changed=lambda _profile: None,
        tts=FakeTTS(),
        stt=FakeSTT(),
    )


def test_voice_command_toggles_runtime_state() -> None:
    services = build_services()

    result = handle_command("/voice on", services=services)

    assert result.handled is True
    assert services.tts.enabled is True
    assert services.renderer.infos[-1].startswith("Voz activada.")


def test_listen_command_injects_transcribed_prompt() -> None:
    services = build_services()

    result = handle_command("/listen", services=services)

    assert result.handled is True
    assert result.injected_prompt == "abre el README"
    assert services.renderer.infos[-1] == "Dictado: abre el README"


def test_voice_note_command_creates_note() -> None:
    services = build_services()

    result = handle_command("/voice-note Libro", services=services)

    assert result.handled is True
    assert services.renderer.infos[-1] == "Nota de voz creada: Libro"


def test_profile_command_switches_active_profile() -> None:
    services = build_services()

    result = handle_command("/profile work", services=services)

    assert result.handled is True
    assert services.profile_manager.active_profile == "work"
    assert services.renderer.infos[-1].startswith("Perfil activo: work")


def test_vault_command_renders_results() -> None:
    services = build_services()

    result = handle_command("/vault acme", services=services)

    assert result.handled is True
    assert "acme.md" in services.renderer.infos[-1]


def test_daily_command_renders_brief(monkeypatch) -> None:
    services = build_services()

    class FakeReport:
        def render(self) -> str:
            return "ADV ARCHON daily brief"

    monkeypatch.setattr(
        "adv_archon.ui.commands.build_daily_brief",
        lambda **_kwargs: FakeReport(),
    )

    result = handle_command("/daily", services=services)

    assert result.handled is True
    assert services.renderer.infos[-1] == "ADV ARCHON daily brief"


def test_daily_command_rejects_invalid_mode() -> None:
    services = build_services()

    result = handle_command("/daily raro", services=services)

    assert result.handled is True
    assert services.renderer.errors[-1] == "Uso: /daily [brief|raw]"
