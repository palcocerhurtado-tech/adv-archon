# mypy: ignore-errors
from __future__ import annotations

import threading
from contextlib import suppress
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from adv_archon.core.config import AppConfig
from adv_archon.core.llm import LLMRouter

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
    detail: str | None = None
    progress: int | None = None
    cancellable: bool = False

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
        if self.detail:
            return self.detail
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

    class DesktopOperationCancelled(RuntimeError):
        pass


    class DesktopRuntimeWorker(QObject):  # type: ignore[misc]
        ready = Signal(str)
        busy_state_changed = Signal(object)
        chunk = Signal(str)
        tool = Signal(str, object)
        context = Signal(object)
        prompt_finished = Signal(str)
        import_finished = Signal(object)
        failed = Signal(str)
        cancelled = Signal(str)
        shutdown_finished = Signal()
        expediente_selected = Signal(object)

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
            self._runtime: Any | None = None
            self._backend_ready = False
            self._cancel_event = threading.Event()  # set from UI thread via DirectConnection
            self._emit_state(
                DesktopBusyState(
                    backend_ready=False,
                    busy=True,
                    task="initializing",
                    detail="Preparando motor…",
                )
            )

        def initialize(self) -> None:
            self._emit_state(
                DesktopBusyState(
                    backend_ready=False,
                    busy=True,
                    task="initializing",
                    detail="Preparando motor…",
                    progress=0,
                )
            )

            def _on_progress(pct: int, detail: str) -> None:
                self._emit_state(
                    DesktopBusyState(
                        backend_ready=False,
                        busy=True,
                        task="initializing",
                        detail=detail,
                        progress=pct,
                    )
                )

            try:
                from adv_archon.core.runtime import ArchonRuntime

                runtime = ArchonRuntime(
                    config=self._config,
                    llm=LLMRouter(self._config.llm),
                    project_root=self._project_root,
                    system_prompt=self._system_prompt,
                    confirm=self._confirm,
                    incognito=self._incognito,
                    progress_callback=_on_progress,
                )
                _on_progress(99, "Aplicando perfil…")
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

        def set_ollama_model(self, model: str) -> None:
            model = model.strip()
            if not model:
                return
            self._config.llm.ollama_model = model
            if self._runtime is not None:
                self._runtime.llm.set_ollama_model(model)
            self._emit_state(DesktopBusyState(backend_ready=self._backend_ready))

        def on_expediente_selected(self, expediente: Any) -> None:
            if self._runtime is not None:
                self._runtime.agent.set_expediente(expediente)

        def run_live_voice(self, max_turns: int) -> None:
            runtime = self._runtime
            if runtime is None or not self._backend_ready:
                self.failed.emit("El backend desktop todavía no está listo.")
                return
            self._cancel_event.clear()
            max_turns = max(1, min(20, int(max_turns)))
            previous_mode = runtime.llm.mode
            runtime.llm.set_mode("local")
            self._mode = runtime.llm.mode
            try:
                from adv_archon.core.llm_types import LLMMessage

                history: list[LLMMessage] = []
                system_prompt = (
                    "Eres ADV ARCHON en modo voz local dentro de la app de escritorio. "
                    "Responde breve, claro y útil. Prioriza expedientes, arquitectura, "
                    "PGOU, tareas y contexto local del usuario."
                )
                runtime.tts.enable()
                self._emit_state(
                    DesktopBusyState(
                        backend_ready=True,
                        busy=True,
                        task="prompt",
                        detail="Modo voz local activo. Escuchando por micrófono…",
                        progress=25,
                        cancellable=True,
                    )
                )
                self.chunk.emit(
                    "Modo voz local activo.\n"
                    "Habla cuando macOS active el micrófono. Di 'salir' para terminar.\n\n"
                )
                for turn in range(max_turns):
                    self._check_cancelled()
                    self._emit_state(
                        DesktopBusyState(
                            backend_ready=True,
                            busy=True,
                            task="prompt",
                            detail=f"Escuchando turno {turn + 1}/{max_turns}…",
                            progress=35,
                            cancellable=True,
                        )
                    )
                    heard = runtime.stt.listen_once()
                    text = heard.text.strip()
                    if not text:
                        self.chunk.emit("No he captado voz suficiente.\n\n")
                        continue
                    self.chunk.emit(f"Tú: {text}\n")
                    if text.casefold() in {"salir", "adiós", "adios", "para", "cancelar"}:
                        break
                    history.append(LLMMessage(role="user", content=text))
                    self._emit_state(
                        DesktopBusyState(
                            backend_ready=True,
                            busy=True,
                            task="prompt",
                            detail="Pensando con Ollama local…",
                            progress=75,
                            cancellable=True,
                        )
                    )
                    response = runtime.llm.complete(
                        history[-8:],
                        system_prompt=system_prompt,
                        task="assistant",
                        prefer_local=True,
                    )
                    answer = response.text.strip()
                    history.append(LLMMessage(role="model", content=answer))
                    self.chunk.emit(f"ARCHON: {answer}\n\n")
                    runtime.tts.speak_async(answer)
                self.chunk.emit("Modo voz local finalizado.")
                self.prompt_finished.emit("Modo voz local finalizado.")
            except DesktopOperationCancelled:
                self.cancelled.emit("Modo voz cancelado por el usuario.")
            except Exception as exc:
                self.failed.emit(f"No se pudo iniciar el modo voz local: {exc}")
            finally:
                runtime.llm.set_mode(previous_mode)
                self._mode = runtime.llm.mode
                self._emit_state(DesktopBusyState(backend_ready=True))

        def run_prompt(self, prompt: str, attachments: list[str]) -> None:
            runtime = self._runtime
            if runtime is None or not self._backend_ready:
                self.failed.emit("El backend desktop todavía no está listo.")
                return
            self._cancel_event.clear()
            attachment_paths = [Path(raw_path) for raw_path in attachments]
            prompt = _enrich_prompt_for_desktop(prompt, attachments)
            has_pdf = any(str(p).lower().endswith(".pdf") for p in attachment_paths)
            initial_detail = (
                "Analizando plano arquitectónico…"
                if has_pdf
                else "Leyendo adjuntos y preparando contexto…"
                if attachment_paths
                else "Analizando petición…"
            )
            initial_progress = 15 if attachment_paths else 5
            self._emit_state(
                DesktopBusyState(
                    backend_ready=True,
                    busy=True,
                    task="prompt",
                    detail=initial_detail,
                    progress=initial_progress,
                    cancellable=True,
                )
            )
            chunks: list[str] = []
            saw_chunks = False

            def on_chunk(chunk: str) -> None:
                nonlocal saw_chunks
                self._check_cancelled()
                if not saw_chunks:
                    saw_chunks = True
                    self._emit_state(
                        DesktopBusyState(
                            backend_ready=True,
                            busy=True,
                            task="prompt",
                            detail="Generando respuesta…",
                            progress=85,
                            cancellable=True,
                        )
                    )
                chunks.append(chunk)
                self.chunk.emit(chunk)

            def on_tool(name: str, arguments: dict[str, object]) -> None:
                self._check_cancelled()
                self._emit_state(
                    DesktopBusyState(
                        backend_ready=True,
                        busy=True,
                        task="prompt",
                        detail=_tool_detail(name, has_attachments=bool(attachment_paths)),
                        progress=_tool_progress(name),
                        cancellable=True,
                    )
                )
                self.tool.emit(name, arguments)

            def on_context(snapshot: object) -> None:
                self._check_cancelled()
                self.context.emit(snapshot)

            try:
                response = runtime.send_prompt(
                    prompt,
                    attachments=attachment_paths,
                    on_tool=on_tool,
                    on_chunk=on_chunk,
                    on_context=on_context,
                )
            except DesktopOperationCancelled:
                self.cancelled.emit("Operación cancelada por el usuario.")
                self._emit_state(DesktopBusyState(backend_ready=True))
                return
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
                DesktopBusyState(
                    backend_ready=True,
                    busy=True,
                    task="knowledge_import",
                    detail="Añadiendo adjuntos al conocimiento…",
                    progress=35,
                )
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
            self._cancel_event.set()        # abort any in-progress prompt immediately
            self._emit_state(
                DesktopBusyState(
                    backend_ready=self._backend_ready,
                    busy=False,
                    task="idle",
                    closing=True,
                    detail="Cerrando…",
                )
            )
            if self._runtime is not None:
                with suppress(Exception):
                    self._runtime.shutdown()
            self.shutdown_finished.emit()
            QThread.currentThread().quit()

        def cancel_prompt(self) -> None:
            self._cancel_event.set()
            self._emit_state(
                DesktopBusyState(
                    backend_ready=self._backend_ready,
                    busy=True,
                    task="prompt",
                    detail="Cancelando petición…",
                    progress=self._last_progress_hint(),
                )
            )

        def _emit_state(self, state: DesktopBusyState) -> None:
            self.busy_state_changed.emit(state)

        def _check_cancelled(self) -> None:
            if self._cancel_event.is_set():
                raise DesktopOperationCancelled

        def _last_progress_hint(self) -> int | None:
            return 90 if self._backend_ready else None

else:

    class DesktopRuntimeWorker:  # type: ignore[no-redef]
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("PySide6 no está instalada. No se puede crear el worker desktop.")


def _tool_progress(name: str) -> int:
    return {
        "read_file": 35,
        "knowledge_search": 45,
        "vault_search": 45,
        "web_search": 55,
        "web_fetch": 65,
        "browser_open": 60,
        "browser_extract": 70,
        "calendar_upcoming": 50,
        "gmail_search": 55,
        "drive_search": 55,
        "notes_create": 80,
        "pgou_add": 40,
        "plan_compliance_check": 70,
        "plan_compliance_check_by_coordinates": 72,
        "plan_compliance_export": 75,
        "pgou_status": 20,
        "pgou_fetch": 50,
        "pgou_fetch_all": 55,
        "pgou_catalogue": 20,
        "resolve_coordinates": 30,
        "site_compliance_context": 35,
    }.get(name, 60)


def _tool_detail(name: str, *, has_attachments: bool) -> str:
    details = {
        "read_file": "Leyendo documento local…",
        "knowledge_search": "Buscando en tu conocimiento local…",
        "vault_search": "Buscando en tus notas Markdown…",
        "web_search": "Buscando contexto externo…",
        "web_fetch": "Leyendo fuente web…",
        "browser_open": "Abriendo página en navegador…",
        "browser_extract": "Extrayendo datos de la página…",
        "calendar_upcoming": "Consultando calendario…",
        "gmail_search": "Triando Gmail…",
        "drive_search": "Buscando en Drive…",
        "notes_create": "Guardando en Notes…",
        "pgou_add": "Indexando normativa urbanística del municipio…",
        "plan_compliance_check": "Analizando cumplimiento normativo del plano…",
        "plan_compliance_check_by_coordinates": (
            "Resolviendo ubicación y analizando cumplimiento normativo…"
        ),
        "plan_compliance_export": "Generando informe PDF de cumplimiento…",
        "pgou_status": "Consultando municipios indexados…",
        "pgou_fetch": "Descargando normativa urbanística desde la fuente oficial…",
        "pgou_fetch_all": "Descargando normativa de todos los municipios del catálogo…",
        "pgou_catalogue": "Consultando catálogo de municipios disponibles…",
        "resolve_coordinates": "Resolviendo coordenadas de la parcela…",
        "site_compliance_context": "Comprobando municipio, catastro y estado PGOU…",
    }
    if name == "read_file" and has_attachments:
        return "Leyendo adjuntos…"
    return details.get(name, "Procesando contexto…")


def _enrich_prompt_for_desktop(prompt: str, attachments: list[str]) -> str:
    """If no text given but PDFs are attached, build a natural compliance prompt."""
    pdf_paths = [p for p in attachments if p.lower().endswith(".pdf")]
    if not pdf_paths:
        return prompt

    stripped = prompt.strip()
    if stripped:
        return prompt

    # User dropped a PDF without writing anything → ask for municipality
    return (
        "He subido un plano arquitectónico en PDF. "
        "¿En qué municipio se ubica el proyecto? "
        "Cuando me lo indiques, analizaré el cumplimiento normativo completo "
        "contra el PGOU de ese municipio."
    )
