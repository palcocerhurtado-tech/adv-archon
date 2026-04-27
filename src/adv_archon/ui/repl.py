from __future__ import annotations

import re
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory, InMemoryHistory

from adv_archon.core.config import AppConfig
from adv_archon.core.context import RuntimeContext
from adv_archon.core.llm import LLMRouter
from adv_archon.core.runtime import ArchonRuntime
from adv_archon.ui.commands import handle_command
from adv_archon.ui.render import Renderer


class ReplApp:
    def __init__(
        self,
        *,
        config: AppConfig,
        llm: LLMRouter,
        project_root: Path,
        system_prompt: str,
        renderer: Renderer,
        incognito: bool = False,
        auto_requested: bool = False,
        listen_requested: bool = False,
    ) -> None:
        self._config = config
        self._llm = llm
        self._project_root = project_root
        self._renderer = renderer
        self._incognito = incognito
        self._listen_requested = listen_requested
        history = InMemoryHistory() if incognito else FileHistory(str(config.paths.history_file))
        self._prompt_session: PromptSession[str] = PromptSession(
            history=history,
        )
        self._runtime = ArchonRuntime(
            config=config,
            llm=llm,
            project_root=project_root,
            system_prompt=system_prompt,
            confirm=self._confirm,
            incognito=incognito,
        )
        self._agent = self._runtime.agent
        self._logger = self._runtime.logger
        self._tts = self._runtime.tts
        self._stt = self._runtime.stt
        self._profile_manager = self._runtime.profile_manager
        self._auto_mode = self._runtime.auto_mode
        self._browser_tools = self._runtime.browser_tools
        self._command_services = self._runtime.build_command_services(self._renderer)
        if auto_requested:
            enabled = self._auto_mode.enable(self._confirm)
            self._logger.log("auto_mode_requested", enabled=enabled)

    def run(self) -> int:
        self._renderer.show_banner(self._build_greeting())
        if self._listen_requested:
            self._handle_startup_listen()
        while True:
            try:
                raw = self._prompt_session.prompt("> ").strip()
            except EOFError:
                self._shutdown()
                self._renderer.show_info("")
                return 0
            except KeyboardInterrupt:
                if self._tts.stop():
                    self._renderer.show_info("Voz detenida.")
                    continue
                self._shutdown()
                self._renderer.show_info("")
                return 0

            if not raw:
                continue

            self._logger.log("user_input", chars=len(raw), slash=raw.startswith("/"))
            try:
                command_result = handle_command(raw, services=self._command_services)
            except KeyboardInterrupt:
                self._renderer.show_info("Escucha cancelada.")
                continue
            except Exception as exc:
                self._renderer.show_error(str(exc))
                continue
            if command_result.handled:
                if command_result.should_exit:
                    self._shutdown()
                    return 0
                if command_result.injected_prompt:
                    self._process_prompt(command_result.injected_prompt)
                continue

            self._process_prompt(raw)

    def ask_once(self, prompt: str) -> int:
        self._logger.log("oneshot_started", chars=len(prompt), mode=self._llm.mode)
        return 0 if self._process_prompt(prompt) else 1

    def _build_greeting(self) -> str:
        return self._runtime.greeting()

    def _runtime_context(self) -> RuntimeContext:
        return self._runtime.runtime_context()

    def _confirm(self, question: str) -> bool:
        answer = self._prompt_session.prompt(f"{question} (y/N) ").strip().lower()
        return answer in {"y", "yes", "s", "si", "sí"}

    def _handle_startup_listen(self) -> None:
        use_wake_word = self._config.voice.wake_word_enabled
        if use_wake_word:
            self._renderer.show_info(
                "Modo escucha activo. "
                f"Esperando wake-word `{self._config.voice.wake_word_keyword}`..."
            )
        else:
            self._renderer.show_info(f"Modo escucha activo. {self._stt.describe()}")
        try:
            result = self._stt.listen_once(use_wake_word=use_wake_word)
        except KeyboardInterrupt:
            self._renderer.show_info("Escucha inicial cancelada.")
            return
        except Exception as exc:
            self._renderer.show_error(str(exc))
            return
        self._renderer.show_info(f"Dictado: {result.text}")
        self._process_prompt(result.text)

    def _process_prompt(self, prompt: str) -> bool:
        normalized_prompt = _normalize_user_prompt(prompt)
        chunks: list[str] = []

        def on_chunk(chunk: str) -> None:
            chunks.append(chunk)
            self._renderer.stream_chunk(chunk)

        try:
            show_context_panel = getattr(self._config.ui, "show_context_panel", True)
            show_tool_input = getattr(self._config.ui, "show_tool_input", False)
            context_callback = (
                self._renderer.show_context_panel if show_context_panel else None
            )
            tool_callback = self._renderer.show_tool if show_tool_input else None
            if hasattr(self, "_runtime"):
                response = self._runtime.send_prompt(
                    normalized_prompt,
                    on_tool=tool_callback,
                    on_chunk=on_chunk,
                    on_context=context_callback,
                )
            else:
                response = self._agent.stream_final_response(
                    normalized_prompt,
                    on_tool=tool_callback,
                    on_chunk=on_chunk,
                    on_context=context_callback,
                )
        except Exception as exc:
            self._renderer.show_error(str(exc))
            return False

        rendered_text = "".join(chunks)
        if rendered_text:
            self._renderer.finish_stream()
        elif response.text:
            self._renderer.show_info(response.text)
            rendered_text = response.text
        self._maybe_speak(rendered_text)
        return True

    def _maybe_speak(self, text: str) -> None:
        try:
            self._tts.speak_async(text)
        except Exception as exc:
            self._renderer.show_error(str(exc))

    def _shutdown(self) -> None:
        self._runtime.shutdown()


def _normalize_user_prompt(prompt: str) -> str:
    stripped = prompt.strip()
    patterns = (
        r'^(?:adv|adv-archon)\s+"(?P<inner>.+)"$',
        r"^(?:adv|adv-archon)\s+'(?P<inner>.+)'$",
    )
    for pattern in patterns:
        match = re.match(pattern, stripped, flags=re.IGNORECASE)
        if match:
            inner = match.group("inner").strip()
            if inner:
                return inner
    return stripped
