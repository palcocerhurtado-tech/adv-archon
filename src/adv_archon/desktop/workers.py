# mypy: ignore-errors
from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from adv_archon.core.config import AppConfig
from adv_archon.core.llm import LLMRouter
from adv_archon.core.runtime import ArchonRuntime

PYSIDE6_AVAILABLE = find_spec("PySide6") is not None

QObject: Any = None
QThread: Any = None
Signal: Any = None

if PYSIDE6_AVAILABLE:
    from PySide6.QtCore import QObject, QThread, Signal


@dataclass(frozen=True, slots=True)
class DesktopBusyState:
    backend_ready: bool
    busy: bool = False
    task: str = "idle"
    closing: bool = False

    @property
    def accepts_user_actions(self) -> bool:
        return not self.busy and not self.closing

    @property
    def can_dispatch_requests(self) -> bool:
        return self.backend_ready and not self.busy and not self.closing

    @property
    def allows_configuration(self) -> bool:
        return not self.busy and not self.closing

    def status_text(self, *, mode: str, profile: str) -> str:
        if self.closing:
            return "Cerrando…"
        if self.task == "initializing":
            return "Preparando motor…"
        if self.task == "prompt":
            return "Procesando petición…"
        if self.task == "knowledge_import":
            return "Añadiendo al conocimiento…"
        if not self.backend_ready:
            return "Esperando backend…"
        return f"Modo: {mode} | Perfil: {profile}"


if PYSIDE6_AVAILABLE:

    class DesktopRuntimeWorker(QObject):  # type: ignore[misc]
        ready = Signal(str)
        busy_state_changed = Signal(object)
        chunk = Signal(str)
        tool = Signal(str, object)
        context = Signal(object)
        prompt_finished = Signal(str)
        import_finished = Signal(object)
        failed = Signal(str)
        shutdown_finished = Signal()

        def __init__(
            self,
            *,
            config: AppConfig,
            project_root: Path,
            system_prompt: str,
            confirm,
            incognito: bool = False,
            initial_mode: str = "local",
            initial_profile: str = "general",
        ) -> None:
            super().__init__()
            self._config = config
            self._project_root = project_root
            self._system_prompt = system_prompt
            self._confirm = confirm
            self._incognito = incognito
            self._mode = initial_mode
            self._profile = initial_profile
            self._runtime: ArchonRuntime | None = None
            self._backend_ready = False
            self._emit_state(DesktopBusyState(backend_ready=False, busy=True, task="initializing"))

        def initialize(self) -> None:
            self._emit_state(DesktopBusyState(backend_ready=False, busy=True, task="initializing"))
            try:
                runtime = ArchonRuntime(
                    config=self._config,
                    llm=LLMRouter(self._config.llm),
                    project_root=self._project_root,
                    system_prompt=self._system_prompt,
                    confirm=self._confirm,
                    incognito=self._incognito,
                )
                runtime.llm.set_mode(self._mode)
                active_profile = runtime.profile_manager.set_active_profile(self._profile)
                runtime.apply_profile(active_profile)
            except Exception as exc:
                self._runtime = None
                self._backend_ready = False
                self._emit_state(DesktopBusyState(backend_ready=False))
                self.failed.emit(str(exc))
                return
            self._runtime = runtime
            self._backend_ready = True
            self._profile = runtime.profile_manager.active_profile
            self._mode = runtime.llm.mode
            self.ready.emit(runtime.greeting())
            self._emit_state(DesktopBusyState(backend_ready=True))

        def set_mode(self, mode: str) -> None:
            self._mode = mode
            if self._runtime is not None:
                self._runtime.llm.set_mode(mode)
                self._mode = self._runtime.llm.mode
            self._emit_state(DesktopBusyState(backend_ready=self._backend_ready))

        def set_profile(self, profile: str) -> None:
            self._profile = profile
            if self._runtime is not None:
                active_profile = self._runtime.profile_manager.set_active_profile(profile)
                self._runtime.apply_profile(active_profile)
                self._profile = active_profile
            self._emit_state(DesktopBusyState(backend_ready=self._backend_ready))

        def run_prompt(self, prompt: str, attachments: list[str]) -> None:
            runtime = self._runtime
            if runtime is None or not self._backend_ready:
                self.failed.emit("El backend desktop todavía no está listo.")
                return
            self._emit_state(DesktopBusyState(backend_ready=True, busy=True, task="prompt"))
            attachment_paths = [Path(raw_path) for raw_path in attachments]
            chunks: list[str] = []

            def on_chunk(chunk: str) -> None:
                chunks.append(chunk)
                self.chunk.emit(chunk)

            def on_tool(name: str, arguments: dict[str, object]) -> None:
                self.tool.emit(name, arguments)

            try:
                response = runtime.send_prompt(
                    prompt,
                    attachments=attachment_paths,
                    on_tool=on_tool,
                    on_chunk=on_chunk,
                    on_context=self.context.emit,
                )
            except Exception as exc:
                self._emit_state(DesktopBusyState(backend_ready=True))
                self.failed.emit(str(exc))
                return

            final_text = "".join(chunks)
            if not final_text and hasattr(response, "text"):
                final_text = str(response.text)
            self.prompt_finished.emit(final_text)
            self._emit_state(DesktopBusyState(backend_ready=True))

        def import_paths(self, paths: list[str]) -> None:
            runtime = self._runtime
            if runtime is None or not self._backend_ready:
                self.failed.emit("El backend desktop todavía no está listo.")
                return
            self._emit_state(
                DesktopBusyState(backend_ready=True, busy=True, task="knowledge_import")
            )
            try:
                result = runtime.import_paths_to_knowledge([Path(raw_path) for raw_path in paths])
            except Exception as exc:
                self._emit_state(DesktopBusyState(backend_ready=True))
                self.failed.emit(str(exc))
                return
            self.import_finished.emit(result)
            self._emit_state(DesktopBusyState(backend_ready=True))

        def shutdown(self) -> None:
            self._emit_state(
                DesktopBusyState(
                    backend_ready=self._backend_ready,
                    busy=False,
                    task="idle",
                    closing=True,
                )
            )
            if self._runtime is not None:
                with suppress(Exception):
                    self._runtime.shutdown()
            self.shutdown_finished.emit()
            QThread.currentThread().quit()

        def _emit_state(self, state: DesktopBusyState) -> None:
            self.busy_state_changed.emit(state)

else:

    class DesktopRuntimeWorker:  # type: ignore[no-redef]
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("PySide6 no está instalada. No se puede crear el worker desktop.")
