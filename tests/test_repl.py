from __future__ import annotations

from types import SimpleNamespace

from adv_archon.core.llm_types import LLMResponse, LLMUsage
from adv_archon.ui.repl import ReplApp


class FakeRenderer:
    def __init__(self) -> None:
        self.infos: list[str] = []
        self.errors: list[str] = []
        self.streamed: list[str] = []
        self.finished = 0
        self.contexts: list[object] = []
        self.tools: list[tuple[str, dict[str, object]]] = []

    def show_info(self, message: str) -> None:
        self.infos.append(message)

    def show_error(self, message: str) -> None:
        self.errors.append(message)

    def stream_chunk(self, chunk: str) -> None:
        self.streamed.append(chunk)

    def finish_stream(self) -> None:
        self.finished += 1

    def show_context_panel(self, snapshot: object) -> None:
        self.contexts.append(snapshot)

    def show_tool(self, name: str, arguments: dict[str, object]) -> None:
        self.tools.append((name, arguments))


class FakeAgent:
    def __init__(self, response: LLMResponse) -> None:
        self.response = response

    def stream_final_response(self, *_args, **kwargs) -> LLMResponse:
        on_context = kwargs.get("on_context")
        on_tool = kwargs.get("on_tool")
        if on_context is not None:
            on_context("contexto")
        if on_tool is not None:
            on_tool("read_file", {"path": "/tmp/demo.pdf"})
        return self.response


class FakeRuntime:
    def __init__(self, response: LLMResponse) -> None:
        self.response = response
        self.prompts: list[str] = []

    def send_prompt(self, prompt: str, **kwargs) -> LLMResponse:
        self.prompts.append(prompt)
        on_context = kwargs.get("on_context")
        if on_context is not None:
            on_context("contexto")
        return self.response


class InterruptingRuntime:
    def send_prompt(self, prompt: str, **_kwargs) -> LLMResponse:
        raise KeyboardInterrupt(prompt)


def test_process_prompt_renders_non_streamed_response() -> None:
    app = ReplApp.__new__(ReplApp)
    app._renderer = FakeRenderer()
    app._agent = FakeAgent(
        LLMResponse(
            text="Puedo ayudarte con calendario, notas y archivos.",
            usage=LLMUsage(),
            provider="deterministic",
            model="capability-handler",
        )
    )
    app._config = SimpleNamespace(ui=SimpleNamespace(show_context_panel=True))
    spoken: list[str] = []
    app._maybe_speak = spoken.append

    result = app._process_prompt("que puedes hacer ?")

    assert result is True
    assert app._renderer.infos[-1] == "Puedo ayudarte con calendario, notas y archivos."
    assert app._renderer.finished == 0
    assert spoken == ["Puedo ayudarte con calendario, notas y archivos."]
    assert app._renderer.errors == []


def test_process_prompt_hides_tool_input_when_disabled() -> None:
    app = ReplApp.__new__(ReplApp)
    app._renderer = FakeRenderer()
    app._agent = FakeAgent(
        LLMResponse(
            text="Resumen listo.",
            usage=LLMUsage(),
            provider="deterministic",
            model="document-handler",
        )
    )
    app._config = SimpleNamespace(
        ui=SimpleNamespace(show_context_panel=True, show_tool_input=False)
    )
    app._maybe_speak = lambda _text: None

    result = app._process_prompt("resume este PDF")

    assert result is True
    assert app._renderer.tools == []


def test_process_prompt_strips_accidental_adv_wrapper() -> None:
    app = ReplApp.__new__(ReplApp)
    app._renderer = FakeRenderer()
    runtime = FakeRuntime(
        LLMResponse(
            text="He guardado el recuerdo.",
            usage=LLMUsage(),
            provider="deterministic",
            model="memory-capture-handler",
        )
    )
    app._runtime = runtime
    app._config = SimpleNamespace(
        ui=SimpleNamespace(show_context_panel=True, show_tool_input=False)
    )
    app._maybe_speak = lambda _text: None

    result = app._process_prompt(
        'adv "recuerda que ahora estoy investigando grimorios, simbolismo y textos esotéricos"'
    )

    assert result is True
    assert runtime.prompts == [
        "recuerda que ahora estoy investigando grimorios, simbolismo y textos esotéricos"
    ]


def test_process_prompt_handles_keyboard_interrupt_gracefully() -> None:
    app = ReplApp.__new__(ReplApp)
    app._renderer = FakeRenderer()
    app._runtime = InterruptingRuntime()
    app._config = SimpleNamespace(
        ui=SimpleNamespace(show_context_panel=True, show_tool_input=False)
    )
    app._maybe_speak = lambda _text: None

    result = app._process_prompt("resume este PDF")

    assert result is False
    assert app._renderer.errors == []
    assert app._renderer.infos[-1] == "Operación cancelada."
