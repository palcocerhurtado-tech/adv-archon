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


def build_services() -> CommandServices:
    return CommandServices(
        llm=FakeLLM(),
        renderer=FakeRenderer(),
        memory=FakeMemory(),
        usage_ledger=FakeUsageLedger(),
        logger=FakeLogger(),
        context_provider=lambda: None,
        confirm=lambda prompt: True,
        recall_limit=5,
        incognito=False,
        auto_mode=FakeAutoMode(),
        shell_tool=FakeShellTool(),
        python_tool=FakePythonTool(),
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
