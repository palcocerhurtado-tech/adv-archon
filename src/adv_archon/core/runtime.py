from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import suppress
from pathlib import Path

from adv_archon.core.agent import Agent, ToolSpec, TurnContextSnapshot
from adv_archon.core.attachments import format_prompt_with_attachments
from adv_archon.core.config import AppConfig
from adv_archon.core.context import RuntimeContext, capture_runtime_context
from adv_archon.core.costs import UsageLedger
from adv_archon.core.knowledge import KnowledgeIndexResult, KnowledgeStore
from adv_archon.core.llm import LLMRouter
from adv_archon.core.llm_types import LLMResponse
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
from adv_archon.tools.guarded_files import FileAccessPolicy, GuardedFileTools
from adv_archon.tools.knowledge_tools import KnowledgeTools, build_knowledge_tool_specs
from adv_archon.tools.mac import MacTools, build_mac_tool_specs
from adv_archon.tools.personal import PersonalTools, build_personal_tool_specs
from adv_archon.tools.python_sandbox import PythonSandboxTool, build_python_tool_specs
from adv_archon.tools.shell import AutoModeManager, ShellPolicy, ShellTool, build_shell_tool_specs
from adv_archon.tools.task_tools import TaskTools, build_task_tool_specs
from adv_archon.tools.web import WebTools
from adv_archon.tools.urban_compliance import UrbanComplianceTools
from adv_archon.tools.web_library_tools import (
    WebLibraryTools,
    build_web_library_tool_specs,
)
from adv_archon.ui.commands import CommandServices
from adv_archon.ui.render import Renderer
from adv_archon.voice.stt import WhisperSpeechToText
from adv_archon.voice.tts import MacTextToSpeech

ConfirmCallback = Callable[[str], bool]


class ArchonRuntime:
    def __init__(
        self,
        *,
        config: AppConfig,
        llm: LLMRouter,
        project_root: Path,
        system_prompt: str,
        confirm: ConfirmCallback,
        incognito: bool = False,
    ) -> None:
        self.config = config
        self.llm = llm
        self.project_root = project_root
        self.system_prompt = system_prompt
        self.incognito = incognito
        self.confirm = confirm

        self.session_store = SessionStore(config.paths.sessions_dir, persist=not incognito)
        self.logger = AppLogger(
            config.paths.logs_dir,
            session_id=self.session_store.session_id,
            persist=not incognito,
        )
        self.usage_ledger = UsageLedger()
        self.auto_mode = AutoModeManager()
        self.shell_policy = ShellPolicy(
            whitelist_commands=config.shell.whitelist_commands,
            timeout_seconds=config.shell.timeout_seconds,
        )
        self.shell_tool = ShellTool(
            policy=self.shell_policy,
            auto_mode=self.auto_mode,
            confirm=confirm,
            logger=self.logger,
            default_cwd=project_root,
        )
        self.python_tool = PythonSandboxTool(
            confirm=confirm,
            logger=self.logger,
            default_cwd=project_root,
        )
        self.mac_tools = MacTools(
            confirm=confirm,
            auto_mode=self.auto_mode,
            shell_policy=self.shell_policy,
            logger=self.logger,
            default_cwd=project_root,
        )

        encoder = SentenceTransformerEncoder(config.memory.embedding_model)
        self.profile_manager = ProfileManager(
            config.paths.profile_state_file,
            default_profile=config.profiles.default_profile,
            definitions=config.profiles.definitions,
        )
        self.tts = MacTextToSpeech(
            enabled=config.voice.enabled,
            voice_name=config.voice.say_voice,
            rate_wpm=config.voice.rate_wpm,
            logger=self.logger,
        )
        self.stt = WhisperSpeechToText(
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
            logger=self.logger,
        )
        self.memory_store = MemoryStore(
            config.paths.memory_db,
            persist=not incognito,
            encoder=encoder,
            logger=self.logger,
        )
        self.knowledge_store = KnowledgeStore(
            config.paths.knowledge_db,
            encoder=encoder,
            default_roots=self.profile_manager.knowledge_roots() or config.knowledge.default_roots,
            vault_roots=self.profile_manager.vault_roots() or config.knowledge.vault_roots,
            auto_index_on_search=config.knowledge.auto_index_on_search,
            max_files_per_root=config.knowledge.max_files_per_root,
            max_file_bytes=config.knowledge.max_file_bytes,
            logger=self.logger,
        )
        self.knowledge_tools = KnowledgeTools(
            self.knowledge_store,
            profile_manager=self.profile_manager,
        )
        file_policy = FileAccessPolicy(
            allowed_roots=tuple(
                Path(item).expanduser().resolve() for item in config.files.allowed_roots
            ),
            sensitive_roots=tuple(
                Path(item).expanduser().resolve() for item in config.files.sensitive_roots
            ),
            allow_sensitive_reads=config.files.allow_sensitive_reads,
        )
        self.file_tools = GuardedFileTools(policy=file_policy)
        self.web_tools = WebTools(
            retry_attempts=config.web.retry_attempts,
            retry_base_delay_seconds=config.web.retry_base_delay_seconds,
            max_concurrency=config.web.max_concurrency,
            min_interval_seconds=config.web.rate_limit_interval_seconds,
        )
        self.web_library_store = WebLibraryStore(
            config.paths.web_library_db,
            encoder=encoder,
            persist=not incognito,
            logger=self.logger,
        )
        self.web_library_tools = WebLibraryTools(self.web_library_store)
        from adv_archon.core.pgou_store import PGOUStore
        self.pgou_store = PGOUStore(config.paths.pgou_db, encoder=encoder)
        self.urban_compliance_tools = UrbanComplianceTools(self.pgou_store, llm)
        self.task_store = TaskStore(
            config.paths.tasks_db,
            timezone_name=config.tasks.default_timezone,
            notifications_enabled=config.tasks.notifications_enabled,
            logger=self.logger,
        )
        self.task_tools = TaskTools(
            self.task_store,
            confirm=confirm,
            allow_mutations=not incognito,
        )
        self.personal_tools = PersonalTools(
            confirm=confirm,
            timezone_name=config.tasks.default_timezone,
            logger=self.logger,
        )
        self.browser_tools = BrowserTools(
            profile_dir=config.paths.browser_profile_dir,
            enabled=config.browser.enabled,
            browser_name=config.browser.browser_name,
            headless=config.browser.headless,
            default_timeout_ms=config.browser.default_timeout_ms,
            rate_limit_interval_seconds=config.browser.rate_limit_interval_seconds,
            retry_attempts=config.browser.retry_attempts,
            retry_base_delay_seconds=config.browser.retry_base_delay_seconds,
            max_concurrency=config.browser.max_concurrency,
            confirm=confirm,
            logger=self.logger,
        )
        self.google_workspace_tools = GoogleWorkspaceTools(
            client_secret_file=config.google.client_secret_file,
            token_file=config.google.token_file,
            confirm=confirm,
            enabled=config.google.enabled,
            timezone_name=config.tasks.default_timezone,
            default_calendar_id=config.google.default_calendar_id,
            gmail_default_max_results=config.google.gmail_default_max_results,
            drive_default_max_results=config.google.drive_default_max_results,
            rate_limit_interval_seconds=config.google.rate_limit_interval_seconds,
            retry_attempts=config.google.retry_attempts,
            retry_base_delay_seconds=config.google.retry_base_delay_seconds,
            max_concurrency=config.google.max_concurrency,
            logger=self.logger,
        )
        self.agent = Agent(
            llm=llm,
            system_prompt=system_prompt,
            session=self.session_store,
            project_root=project_root,
            max_tool_steps=config.ui.max_tool_steps,
            operator_max_tool_steps=config.ui.operator_max_tool_steps,
            context_provider=self.runtime_context,
            memory_store=self.memory_store,
            knowledge_store=self.knowledge_store,
            usage_callback=self.record_usage,
            auto_recall_limit=config.memory.auto_recall_limit,
            auto_knowledge_limit=config.knowledge.search_limit,
            force_local_private_context=config.llm.force_local_private_context,
            extra_tools=self.build_agent_tools(),
        )
        self.logger.log(
            "session_started",
            cwd=project_root,
            incognito=incognito,
            mode=self.llm.mode,
            active_profile=self.profile_manager.active_profile,
            voice_enabled=config.voice.enabled,
        )

    def greeting(self) -> str:
        return self.runtime_context().greeting()

    def runtime_context(self) -> RuntimeContext:
        return capture_runtime_context(
            self.project_root,
            active_profile=self.profile_manager.active_profile,
        )

    def send_prompt(
        self,
        prompt: str,
        *,
        attachments: Sequence[Path | str] | None = None,
        on_tool: Callable[[str, dict[str, object]], None] | None = None,
        on_chunk: Callable[[str], None] | None = None,
        on_context: Callable[[TurnContextSnapshot], None] | None = None,
    ) -> LLMResponse:
        resolved_attachments = list(attachments or ())
        enriched_prompt = _maybe_build_compliance_prompt(
            prompt, resolved_attachments, self.urban_compliance_tools
        )
        final_prompt = format_prompt_with_attachments(enriched_prompt, resolved_attachments)
        return self.agent.stream_final_response(
            final_prompt,
            on_tool=on_tool,
            on_chunk=on_chunk,
            on_context=on_context,
        )

    def import_paths_to_knowledge(
        self,
        paths: Sequence[Path | str],
        *,
        refresh: bool = True,
    ) -> KnowledgeIndexResult:
        return self.knowledge_store.index_paths(paths, refresh=refresh)

    def build_command_services(self, renderer: Renderer) -> CommandServices:
        return CommandServices(
            llm=self.llm,
            renderer=renderer,
            memory=self.memory_store,
            task_store=self.task_store,
            task_tools=self.task_tools,
            personal_tools=self.personal_tools,
            google_workspace_tools=self.google_workspace_tools,
            knowledge_store=self.knowledge_store,
            usage_ledger=self.usage_ledger,
            logger=self.logger,
            context_provider=self.runtime_context,
            project_root=self.project_root,
            logs_dir=self.config.paths.logs_dir,
            confirm=self.confirm,
            recall_limit=self.config.memory.slash_recall_limit,
            incognito=self.incognito,
            auto_mode=self.auto_mode,
            shell_tool=self.shell_tool,
            python_tool=self.python_tool,
            knowledge_tools=self.knowledge_tools,
            file_tools=self.file_tools,
            web_tools=self.web_tools,
            profile_manager=self.profile_manager,
            on_profile_changed=self.apply_profile,
            tts=self.tts,
            stt=self.stt,
            urban_compliance_tools=self.urban_compliance_tools,
        )

    def apply_profile(self, profile_name: str) -> None:
        profile_roots = self.profile_manager.knowledge_roots(profile_name)
        vault_roots = self.profile_manager.vault_roots(profile_name)
        if profile_roots:
            self.knowledge_store.set_default_roots(profile_roots)
        else:
            self.knowledge_store.set_default_roots(self.config.knowledge.default_roots)
        if vault_roots:
            self.knowledge_store.set_vault_roots(vault_roots)
        else:
            self.knowledge_store.set_vault_roots(self.config.knowledge.vault_roots)

    def shutdown(self) -> None:
        self.tts.stop()
        with suppress(Exception):
            self.browser_tools.browser_close()

    def record_usage(self, phase: str, response: object) -> None:
        from adv_archon.core.llm_types import LLMResponse

        llm_response = response
        if not isinstance(llm_response, LLMResponse):
            return
        event = self.usage_ledger.record(phase, llm_response)
        self.logger.log(
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

    def build_agent_tools(self) -> list[ToolSpec]:
        specs: list[ToolSpec] = []
        specs.extend(
            [
                ToolSpec(
                    name="read_file",
                    description=(
                        "Read a local file under the configured directory guardrails. "
                        "Supports text, markdown, PDFs, images with OCR, and office docs."
                    ),
                    schema={
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "start_line": {"type": "integer"},
                            "end_line": {"type": "integer"},
                            "preview": {"type": "boolean"},
                        },
                        "required": ["path"],
                    },
                    fn=self.file_tools.read_file,
                ),
                ToolSpec(
                    name="list_dir",
                    description="List a directory under the configured directory guardrails.",
                    schema={
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "depth": {"type": "integer"},
                        },
                        "required": ["path"],
                    },
                    fn=self.file_tools.list_dir,
                ),
                ToolSpec(
                    name="find_local",
                    description=(
                        "Find local files or folders under the configured directory guardrails."
                    ),
                    schema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "path": {"type": "string"},
                            "folder_hint": {"type": "string"},
                            "kind": {"type": "string"},
                            "max_results": {"type": "integer"},
                        },
                        "required": ["query"],
                    },
                    fn=self.file_tools.find_local,
                ),
                ToolSpec(
                    name="web_search",
                    description="Search the web with retries, backoff and concurrency caps.",
                    schema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "n": {"type": "integer"},
                        },
                        "required": ["query"],
                    },
                    fn=self.web_tools.web_search,
                ),
                ToolSpec(
                    name="web_fetch",
                    description="Fetch and clean the main text of a webpage with retries.",
                    schema={
                        "type": "object",
                        "properties": {"url": {"type": "string"}},
                        "required": ["url"],
                    },
                    fn=self.web_tools.web_fetch,
                ),
            ]
        )
        for definition in build_shell_tool_specs(self.shell_tool):
            specs.append(
                ToolSpec(
                    name=definition["name"],
                    description=definition["description"],
                    schema=definition["schema"],
                    fn=definition["fn"],
                )
            )
        for definition in build_python_tool_specs(self.python_tool):
            specs.append(
                ToolSpec(
                    name=definition["name"],
                    description=definition["description"],
                    schema=definition["schema"],
                    fn=definition["fn"],
                )
            )
        for definition in build_mac_tool_specs(self.mac_tools):
            specs.append(
                ToolSpec(
                    name=definition["name"],
                    description=definition["description"],
                    schema=definition["schema"],
                    fn=definition["fn"],
                )
            )
        for definition in build_task_tool_specs(self.task_tools):
            specs.append(
                ToolSpec(
                    name=definition["name"],
                    description=definition["description"],
                    schema=definition["schema"],
                    fn=definition["fn"],
                )
            )
        for definition in build_personal_tool_specs(self.personal_tools):
            specs.append(
                ToolSpec(
                    name=definition["name"],
                    description=definition["description"],
                    schema=definition["schema"],
                    fn=definition["fn"],
                )
            )
        for definition in build_browser_tool_specs(self.browser_tools):
            specs.append(
                ToolSpec(
                    name=definition["name"],
                    description=definition["description"],
                    schema=definition["schema"],
                    fn=definition["fn"],
                )
            )
        for definition in build_google_workspace_tool_specs(self.google_workspace_tools):
            specs.append(
                ToolSpec(
                    name=definition["name"],
                    description=definition["description"],
                    schema=definition["schema"],
                    fn=definition["fn"],
                )
            )
        for definition in build_knowledge_tool_specs(self.knowledge_tools):
            specs.append(
                ToolSpec(
                    name=definition["name"],
                    description=definition["description"],
                    schema=definition["schema"],
                    fn=definition["fn"],
                )
            )
        for definition in build_web_library_tool_specs(self.web_library_tools):
            specs.append(
                ToolSpec(
                    name=definition["name"],
                    description=definition["description"],
                    schema=definition["schema"],
                    fn=definition["fn"],
                )
            )
        for definition in _build_urban_compliance_tool_specs(self.urban_compliance_tools):
            specs.append(
                ToolSpec(
                    name=definition["name"],
                    description=definition["description"],
                    schema=definition["schema"],
                    fn=definition["fn"],
                )
            )
        return specs


def _maybe_build_compliance_prompt(
    prompt: str,
    attachments: list,
    compliance_tools: "UrbanComplianceTools",
) -> str:
    """If the request looks like a plan compliance check, build a rich operator prompt."""
    from adv_archon.core.intent import COMPLIANCE_KEYWORDS, extract_municipality, _normalize

    pdf_paths = [
        str(p) for p in attachments
        if str(p).lower().endswith(".pdf")
    ]
    if not pdf_paths:
        return prompt

    text_lower = _normalize(prompt)
    is_compliance = any(kw.replace("á","a").replace("é","e").replace("í","i")
                        .replace("ó","o").replace("ú","u") in text_lower
                        for kw in COMPLIANCE_KEYWORDS)
    if not is_compliance:
        return prompt

    municipality = extract_municipality(prompt)
    plan_path = pdf_paths[0]

    if municipality is None:
        return (
            f"{prompt}\n\n"
            "INSTRUCCIÓN INTERNA: Se ha detectado un plano PDF y keywords de normativa urbanística. "
            "Pregunta al usuario en qué municipio se ubica el proyecto antes de continuar "
            "con el análisis de cumplimiento normativo."
        )

    muni_status = compliance_tools.pgou_status()
    indexed = [m["name"].lower() for m in muni_status.payload.get("municipalities", [])]
    municipality_indexed = municipality.lower() in indexed

    if not municipality_indexed:
        return (
            f"{prompt}\n\n"
            "INSTRUCCIÓN INTERNA: Flujo de análisis normativo activado automáticamente.\n"
            f"Municipio detectado: {municipality}\n"
            f"Plano PDF: {plan_path}\n\n"
            f"PASO 1: La normativa de {municipality} no está indexada todavía. "
            f"Busca en la web el PGOU o las normas urbanísticas oficiales de {municipality} "
            f"(portal web del ayuntamiento, BOE, boletín oficial de la comunidad autónoma). "
            f"Descarga el texto y usa pgou_add con municipality='{municipality}'. "
            f"PASO 2: Una vez indexado, usa plan_compliance_check con "
            f"plan_path='{plan_path}' y municipality='{municipality}'. "
            "PASO 3: Presenta el informe de cumplimiento de forma clara, con tabla de "
            "parámetros (altura, superficies, retranqueos, usos) indicando ✓/⚠/✗ para cada uno."
        )

    wants_pdf = any(w in _normalize(prompt) for w in
                    ("informe", "pdf", "exporta", "genera", "descarga", "report", "documento"))

    tool_name = "plan_compliance_export" if wants_pdf else "plan_compliance_check"
    extra = (
        " El informe PDF se guardará en el Escritorio automáticamente."
        if wants_pdf else
        " Presenta el informe con tabla de parámetros (altura, superficies, "
        "retranqueos, usos) indicando ✓/⚠/✗ para cada uno."
    )

    return (
        f"{prompt}\n\n"
        "INSTRUCCIÓN INTERNA: Flujo de análisis normativo activado automáticamente.\n"
        f"Municipio detectado: {municipality} (normativa ya indexada ✓)\n"
        f"Plano PDF: {plan_path}\n\n"
        f"Usa {tool_name} con plan_path='{plan_path}' y municipality='{municipality}'."
        f"{extra}"
    )


def _build_urban_compliance_tool_specs(
    tools: "UrbanComplianceTools",
) -> list[dict]:
    return [
        {
            "name": "pgou_add",
            "description": (
                "Index the text of a municipal PGOU (urban planning regulation) "
                "so it can be used for compliance analysis. "
                "Pass the full text of the regulation and the municipality name."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "municipality": {
                        "type": "string",
                        "description": "Municipality name, e.g. 'Madrid', 'Barcelona'.",
                    },
                    "text": {
                        "type": "string",
                        "description": "Full text of the PGOU or urban regulation.",
                    },
                    "source": {
                        "type": "string",
                        "description": "Origin URL or file path of the regulation document.",
                    },
                },
                "required": ["municipality", "text"],
            },
            "fn": tools.pgou_add,
        },
        {
            "name": "plan_compliance_check",
            "description": (
                "Analyze an architectural plan PDF against the indexed PGOU of a municipality. "
                "Returns a compliance report with annotations about heights, areas, setbacks, "
                "land use, and buildability rules."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "plan_path": {
                        "type": "string",
                        "description": "Absolute or ~ path to the architectural plan PDF.",
                    },
                    "municipality": {
                        "type": "string",
                        "description": "Municipality whose PGOU to check against.",
                    },
                },
                "required": ["plan_path", "municipality"],
            },
            "fn": tools.plan_compliance_check,
        },
        {
            "name": "pgou_status",
            "description": "List all municipalities with indexed PGOU regulations.",
            "schema": {"type": "object", "properties": {}, "required": []},
            "fn": tools.pgou_status,
        },
        {
            "name": "plan_compliance_export",
            "description": (
                "Run a full compliance check on an architectural plan PDF and export the result "
                "as a professional PDF report ready to share with clients or submit to the council. "
                "Saves the PDF to the Desktop by default."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "plan_path": {
                        "type": "string",
                        "description": "Path to the architectural plan PDF.",
                    },
                    "municipality": {
                        "type": "string",
                        "description": "Municipality whose PGOU to check against.",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Optional output path for the PDF report.",
                    },
                },
                "required": ["plan_path", "municipality"],
            },
            "fn": tools.plan_compliance_export,
        },
        {
            "name": "pgou_fetch",
            "description": (
                "Automatically download and index the PGOU (urban planning regulation) "
                "for a municipality from its official source. "
                "Use this instead of pgou_add when the user asks to fetch, download, or "
                "auto-index a municipality's regulations."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "municipality": {
                        "type": "string",
                        "description": "Municipality name, e.g. 'Madrid', 'Sevilla'.",
                    },
                },
                "required": ["municipality"],
            },
            "fn": tools.pgou_fetch,
        },
        {
            "name": "pgou_fetch_all",
            "description": (
                "Automatically download and index PGOU regulations for all municipalities "
                "in the catalogue. Skips already-indexed municipalities by default."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "skip_indexed": {
                        "type": "boolean",
                        "description": "If true (default), skip municipalities already indexed.",
                    },
                },
                "required": [],
            },
            "fn": tools.pgou_fetch_all,
        },
        {
            "name": "pgou_catalogue",
            "description": (
                "List all municipalities available for automatic PGOU fetching, "
                "showing which are already indexed."
            ),
            "schema": {"type": "object", "properties": {}, "required": []},
            "fn": tools.pgou_catalogue,
        },
    ]
