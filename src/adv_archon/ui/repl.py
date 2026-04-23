from __future__ import annotations

from contextlib import suppress
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory, InMemoryHistory

from adv_archon.core.agent import Agent, ToolSpec
from adv_archon.core.config import AppConfig
from adv_archon.core.context import RuntimeContext, capture_runtime_context
from adv_archon.core.costs import UsageLedger
from adv_archon.core.knowledge import KnowledgeStore
from adv_archon.core.llm import LLMRouter
from adv_archon.core.logging import AppLogger
from adv_archon.core.memory import MemoryStore, SentenceTransformerEncoder
from adv_archon.core.profiles import ProfileManager
from adv_archon.core.session import SessionStore
from adv_archon.core.tasks import TaskStore
from adv_archon.core.web_library import WebLibraryStore
from adv_archon.tools.browser import BrowserTools, build_browser_tool_specs
from adv_archon.tools.google_workspace import (
    GoogleWorkspaceTools,
    build_google_workspace_tool_specs,
)
from adv_archon.tools.knowledge_tools import KnowledgeTools, build_knowledge_tool_specs
from adv_archon.tools.mac import MacTools, build_mac_tool_specs
from adv_archon.tools.personal import PersonalTools, build_personal_tool_specs
from adv_archon.tools.python_sandbox import PythonSandboxTool, build_python_tool_specs
from adv_archon.tools.shell import AutoModeManager, ShellPolicy, ShellTool, build_shell_tool_specs
from adv_archon.tools.task_tools import TaskTools, build_task_tool_specs
from adv_archon.tools.web_library_tools import (
    WebLibraryTools,
    build_web_library_tool_specs,
)
from adv_archon.ui.commands import CommandServices, handle_command
from adv_archon.ui.render import Renderer
from adv_archon.voice.stt import WhisperSpeechToText
from adv_archon.voice.tts import MacTextToSpeech


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
        self._session_store = SessionStore(config.paths.sessions_dir, persist=not incognito)
        self._logger = AppLogger(
            config.paths.logs_dir,
            session_id=self._session_store.session_id,
            persist=not incognito,
        )
        self._usage_ledger = UsageLedger()
        self._auto_mode = AutoModeManager()
        self._shell_policy = ShellPolicy(
            whitelist_commands=config.shell.whitelist_commands,
            timeout_seconds=config.shell.timeout_seconds,
        )
        history = InMemoryHistory() if incognito else FileHistory(str(config.paths.history_file))
        self._prompt_session: PromptSession[str] = PromptSession(
            history=history,
        )
        self._shell_tool = ShellTool(
            policy=self._shell_policy,
            auto_mode=self._auto_mode,
            confirm=self._confirm,
            logger=self._logger,
            default_cwd=project_root,
        )
        self._python_tool = PythonSandboxTool(
            confirm=self._confirm,
            logger=self._logger,
            default_cwd=project_root,
        )
        self._mac_tools = MacTools(
            confirm=self._confirm,
            auto_mode=self._auto_mode,
            shell_policy=self._shell_policy,
            logger=self._logger,
            default_cwd=project_root,
        )
        encoder = SentenceTransformerEncoder(config.memory.embedding_model)
        self._profile_manager = ProfileManager(
            config.paths.profile_state_file,
            default_profile=config.profiles.default_profile,
            definitions=config.profiles.definitions,
        )
        self._tts = MacTextToSpeech(
            enabled=config.voice.enabled,
            voice_name=config.voice.say_voice,
            rate_wpm=config.voice.rate_wpm,
            logger=self._logger,
        )
        self._stt = WhisperSpeechToText(
            model_name=config.voice.stt_model,
            language=config.voice.stt_language,
            device=config.voice.stt_device,
            compute_type=config.voice.stt_compute_type,
            sample_rate=config.voice.sample_rate,
            max_record_seconds=config.voice.max_record_seconds,
            silence_seconds=config.voice.silence_seconds,
            silence_threshold=config.voice.silence_threshold,
            wake_word_enabled=config.voice.wake_word_enabled,
            wake_word_keyword=config.voice.wake_word_keyword,
            wake_word_timeout_seconds=config.voice.wake_word_timeout_seconds,
            porcupine_access_key=config.voice.porcupine_access_key,
            logger=self._logger,
        )
        self._memory_store = MemoryStore(
            config.paths.memory_db,
            persist=not incognito,
            encoder=encoder,
            logger=self._logger,
        )
        self._knowledge_store = KnowledgeStore(
            config.paths.knowledge_db,
            encoder=encoder,
            default_roots=self._profile_manager.knowledge_roots() or config.knowledge.default_roots,
            vault_roots=self._profile_manager.vault_roots() or config.knowledge.vault_roots,
            auto_index_on_search=config.knowledge.auto_index_on_search,
            max_files_per_root=config.knowledge.max_files_per_root,
            max_file_bytes=config.knowledge.max_file_bytes,
            logger=self._logger,
        )
        self._knowledge_tools = KnowledgeTools(
            self._knowledge_store,
            profile_manager=self._profile_manager,
        )
        self._web_library_store = WebLibraryStore(
            config.paths.web_library_db,
            encoder=encoder,
            persist=not incognito,
            logger=self._logger,
        )
        self._web_library_tools = WebLibraryTools(self._web_library_store)
        self._task_store = TaskStore(
            config.paths.tasks_db,
            timezone_name=config.tasks.default_timezone,
            notifications_enabled=config.tasks.notifications_enabled,
            logger=self._logger,
        )
        self._task_tools = TaskTools(
            self._task_store,
            confirm=self._confirm,
            allow_mutations=not incognito,
        )
        self._personal_tools = PersonalTools(
            confirm=self._confirm,
            timezone_name=config.tasks.default_timezone,
            logger=self._logger,
        )
        self._browser_tools = BrowserTools(
            profile_dir=config.paths.browser_profile_dir,
            enabled=config.browser.enabled,
            browser_name=config.browser.browser_name,
            headless=config.browser.headless,
            default_timeout_ms=config.browser.default_timeout_ms,
            confirm=self._confirm,
            logger=self._logger,
        )
        self._google_workspace_tools = GoogleWorkspaceTools(
            client_secret_file=config.google.client_secret_file,
            token_file=config.google.token_file,
            confirm=self._confirm,
            enabled=config.google.enabled,
            timezone_name=config.tasks.default_timezone,
            default_calendar_id=config.google.default_calendar_id,
            gmail_default_max_results=config.google.gmail_default_max_results,
            drive_default_max_results=config.google.drive_default_max_results,
            logger=self._logger,
        )
        self._agent = Agent(
            llm=llm,
            system_prompt=system_prompt,
            session=self._session_store,
            project_root=project_root,
            max_tool_steps=config.ui.max_tool_steps,
            operator_max_tool_steps=config.ui.operator_max_tool_steps,
            context_provider=self._runtime_context,
            memory_store=self._memory_store,
            knowledge_store=self._knowledge_store,
            usage_callback=self._record_usage,
            auto_recall_limit=config.memory.auto_recall_limit,
            auto_knowledge_limit=config.knowledge.search_limit,
            force_local_private_context=config.llm.force_local_private_context,
            extra_tools=self._build_agent_tools(),
        )
        self._command_services = CommandServices(
            llm=self._llm,
            renderer=self._renderer,
            memory=self._memory_store,
            usage_ledger=self._usage_ledger,
            logger=self._logger,
            context_provider=self._runtime_context,
            confirm=self._confirm,
            recall_limit=config.memory.slash_recall_limit,
            incognito=incognito,
            auto_mode=self._auto_mode,
            shell_tool=self._shell_tool,
            python_tool=self._python_tool,
            knowledge_tools=self._knowledge_tools,
            profile_manager=self._profile_manager,
            on_profile_changed=self._apply_profile,
            tts=self._tts,
            stt=self._stt,
        )
        self._logger.log(
            "session_started",
            cwd=project_root,
            incognito=incognito,
            mode=self._llm.mode,
            active_profile=self._profile_manager.active_profile,
            voice_enabled=config.voice.enabled,
        )
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
        return self._runtime_context().greeting()

    def _runtime_context(self) -> RuntimeContext:
        return capture_runtime_context(
            self._project_root,
            active_profile=self._profile_manager.active_profile,
        )

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
        chunks: list[str] = []

        def on_chunk(chunk: str) -> None:
            chunks.append(chunk)
            self._renderer.stream_chunk(chunk)

        try:
            self._agent.stream_final_response(
                prompt,
                on_tool=self._renderer.show_tool,
                on_chunk=on_chunk,
                on_context=self._renderer.show_context_panel
                if self._config.ui.show_context_panel
                else None,
            )
        except Exception as exc:
            self._renderer.show_error(str(exc))
            return False

        self._renderer.finish_stream()
        self._maybe_speak("".join(chunks))
        return True

    def _maybe_speak(self, text: str) -> None:
        try:
            self._tts.speak_async(text)
        except Exception as exc:
            self._renderer.show_error(str(exc))

    def _shutdown(self) -> None:
        self._tts.stop()
        with suppress(Exception):
            self._browser_tools.browser_close()

    def _record_usage(self, phase: str, response: object) -> None:
        from adv_archon.core.llm_types import LLMResponse

        llm_response = response
        if not isinstance(llm_response, LLMResponse):
            return
        event = self._usage_ledger.record(phase, llm_response)
        self._logger.log(
            "llm_call",
            phase=event.phase,
            provider=event.provider,
            model=event.model,
            prompt_tokens=event.prompt_tokens,
            completion_tokens=event.completion_tokens,
            total_tokens=event.total_tokens,
            estimated_cost_usd=event.estimated_cost_usd,
            redaction_applied=event.redaction_applied,
            redaction_items=event.redaction_items,
        )

    def _apply_profile(self, profile_name: str) -> None:
        profile_roots = self._profile_manager.knowledge_roots(profile_name)
        vault_roots = self._profile_manager.vault_roots(profile_name)
        if profile_roots:
            self._knowledge_store.set_default_roots(profile_roots)
        else:
            self._knowledge_store.set_default_roots(self._config.knowledge.default_roots)
        if vault_roots:
            self._knowledge_store.set_vault_roots(vault_roots)
        else:
            self._knowledge_store.set_vault_roots(self._config.knowledge.vault_roots)

    def _build_agent_tools(self) -> list[ToolSpec]:
        specs: list[ToolSpec] = []
        for definition in build_shell_tool_specs(self._shell_tool):
            specs.append(
                ToolSpec(
                    name=definition["name"],
                    description=definition["description"],
                    schema=definition["schema"],
                    fn=definition["fn"],
                )
            )
        for definition in build_python_tool_specs(self._python_tool):
            specs.append(
                ToolSpec(
                    name=definition["name"],
                    description=definition["description"],
                    schema=definition["schema"],
                    fn=definition["fn"],
                )
            )
        for definition in build_mac_tool_specs(self._mac_tools):
            specs.append(
                ToolSpec(
                    name=definition["name"],
                    description=definition["description"],
                    schema=definition["schema"],
                    fn=definition["fn"],
                )
            )
        for definition in build_task_tool_specs(self._task_tools):
            specs.append(
                ToolSpec(
                    name=definition["name"],
                    description=definition["description"],
                    schema=definition["schema"],
                    fn=definition["fn"],
                )
            )
        for definition in build_personal_tool_specs(self._personal_tools):
            specs.append(
                ToolSpec(
                    name=definition["name"],
                    description=definition["description"],
                    schema=definition["schema"],
                    fn=definition["fn"],
                )
            )
        for definition in build_browser_tool_specs(self._browser_tools):
            specs.append(
                ToolSpec(
                    name=definition["name"],
                    description=definition["description"],
                    schema=definition["schema"],
                    fn=definition["fn"],
                )
            )
        for definition in build_google_workspace_tool_specs(self._google_workspace_tools):
            specs.append(
                ToolSpec(
                    name=definition["name"],
                    description=definition["description"],
                    schema=definition["schema"],
                    fn=definition["fn"],
                )
            )
        for definition in build_knowledge_tool_specs(self._knowledge_tools):
            specs.append(
                ToolSpec(
                    name=definition["name"],
                    description=definition["description"],
                    schema=definition["schema"],
                    fn=definition["fn"],
                )
            )
        for definition in build_web_library_tool_specs(self._web_library_tools):
            specs.append(
                ToolSpec(
                    name=definition["name"],
                    description=definition["description"],
                    schema=definition["schema"],
                    fn=definition["fn"],
                )
            )
        return specs
