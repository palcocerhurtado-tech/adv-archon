from pathlib import Path
from types import SimpleNamespace

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
    def __init__(self) -> None:
        self.records = [
            SimpleNamespace(
                id=1,
                content="Investigo grimorios y simbolismo",
                tags=["study"],
                score=0.9,
                memory_type="preference",
                namespace="general",
                category="interests",
                importance=5,
            )
        ]

    def recall(self, _query: str, limit: int = 5, **_kwargs) -> list[object]:
        return self.records[:limit]

    def find_matches(self, _query: str, limit: int = 5) -> list[object]:
        return self.records[:limit]

    def forget_by_ids(self, ids: list[int]) -> int:
        return len(ids)

    def list_memories(self, limit: int = 20, **_kwargs) -> list[object]:
        return self.records[:limit]

    def remember(
        self,
        content: str,
        *_args,
        category: str = "general",
        importance: int = 3,
        **_kwargs,
    ):
        record = SimpleNamespace(
            id=len(self.records) + 1,
            content=content,
            tags=[category],
            score=None,
            memory_type="preference",
            namespace="general",
            category=category,
            importance=importance,
        )
        self.records.append(record)
        return record

    def update_memory(self, memory_id: int, **kwargs) -> object:
        for record in self.records:
            if record.id == memory_id:
                if kwargs.get("content") is not None:
                    record.content = kwargs["content"]
                if kwargs.get("category") is not None:
                    record.category = kwargs["category"]
                if kwargs.get("importance") is not None:
                    record.importance = kwargs["importance"]
                return record
        raise LookupError(memory_id)


class FakeTaskStore:
    def list_tasks(self, *_, **__) -> list[object]:
        return [
            SimpleNamespace(
                id=7,
                title="Bloque de estudio",
                due_at="2026-04-29T19:30:00+02:00",
                status="scheduled",
                category="study",
                source="automation:executive_assistant:study_review",
            )
        ]


class FakeTaskTools:
    def task_list_automation_presets(self) -> object:
        return SimpleNamespace(
            payload={
                "presets": [
                    {
                        "name": "Executive Assistant",
                        "description": "Automatización local.",
                        "launch_workflows": [
                            {"title": "Briefing", "times": ["08:00"], "interval_minutes": None},
                            {"title": "Prep reuniones", "times": [], "interval_minutes": 15},
                        ],
                    }
                ]
            }
        )

    def task_install_executive_automation(self, study_focus: str = "") -> object:
        return SimpleNamespace(
            payload={
                "bundle": "executive_assistant",
                "launch_agents": [{"label": "com.adv-archon.exec", "plist_path": "/tmp/a.plist"}],
                "tasks": [
                    {
                        "title": f"Bloque de estudio | {study_focus or 'general'}",
                        "due_at": "2026-04-29 19:30",
                    }
                ],
            }
        )


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


class FakeUrbanComplianceTools:
    pass


class FakeGeoTools:
    pass


def build_services() -> CommandServices:
    return CommandServices(
        llm=FakeLLM(),
        renderer=FakeRenderer(),
        memory=FakeMemory(),
        task_store=FakeTaskStore(),
        task_tools=FakeTaskTools(),
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
        urban_compliance_tools=FakeUrbanComplianceTools(),
        geo_tools=FakeGeoTools(),
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


def test_memory_command_lists_overview() -> None:
    services = build_services()

    result = handle_command("/memory", services=services)

    assert result.handled is True
    assert "Estado de memoria:" in services.renderer.infos[-1]
    assert "interests" in services.renderer.infos[-1]


def test_memory_command_can_remember_new_item() -> None:
    services = build_services()

    result = handle_command(
        "/memory remember interests | Estoy investigando textos herméticos",
        services=services,
    )

    assert result.handled is True
    assert "He guardado" in services.renderer.infos[-1]


def test_pgou_check_coords_command_injects_coordinate_analysis_prompt() -> None:
    services = build_services()

    result = handle_command(
        "/pgou check-coords 40.4168 -3.7038 ~/Desktop/plano.pdf",
        services=services,
    )

    assert result.handled is True
    assert result.injected_prompt is not None
    assert "plan_compliance_check_by_coordinates" in result.injected_prompt
    assert "40.4168" in result.injected_prompt
    assert "-3.7038" in result.injected_prompt


def test_pgou_locate_command_mentions_legal_pending_checks() -> None:
    services = build_services()

    result = handle_command("/pgou locate 40.4168 -3.7038", services=services)

    assert result.handled is True
    assert result.injected_prompt is not None
    assert "site_compliance_context" in result.injected_prompt
    assert "advertencias sectoriales" in result.injected_prompt


def test_automation_command_shows_status() -> None:
    services = build_services()

    result = handle_command("/automation", services=services)

    assert result.handled is True
    assert "Automatización ejecutiva:" in services.renderer.infos[-1]


def test_automation_install_command_renders_result() -> None:
    services = build_services()

    result = handle_command("/automation install grimorios", services=services)

    assert result.handled is True
    assert "Automatización ejecutiva instalada." in services.renderer.infos[-1]
    assert "Bloque de estudio | grimorios" in services.renderer.infos[-1]


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


def test_briefing_command_injects_executive_prompt() -> None:
    services = build_services()

    result = handle_command("/briefing", services=services)

    assert result.handled is True
    assert (
        result.injected_prompt
        == "dame un briefing ejecutivo del día con agenda, inbox y prioridades"
    )
