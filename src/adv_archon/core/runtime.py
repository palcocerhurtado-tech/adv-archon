from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any

from adv_archon.core.agent import Agent, ToolSpec, TurnContextSnapshot
from adv_archon.core.attachments import format_prompt_with_attachments
from adv_archon.core.config import AppConfig
from adv_archon.core.context import RuntimeContext, capture_runtime_context
from adv_archon.core.costs import UsageLedger
from adv_archon.core.informe_proyecto import InformeProyectoTools
from adv_archon.core.intent import (
    _normalize,
    extract_municipality,
    looks_like_compliance_request,
)
from adv_archon.core.knowledge import KnowledgeIndexResult, KnowledgeStore
from adv_archon.core.llm import LLMRouter
from adv_archon.core.llm_types import LLMResponse
from adv_archon.core.logging import AppLogger
from adv_archon.core.memoria_descriptiva import MemoriaDescriptivaTools
from adv_archon.core.memoria_pdf import MemoriaPDFTools
from adv_archon.core.memory import MemoryStore, SentenceTransformerEncoder
from adv_archon.core.pem_pdf import PEMPDFTools
from adv_archon.core.profiles import ProfileManager
from adv_archon.core.session import SessionStore
from adv_archon.core.tasks import TaskStore
from adv_archon.core.team_sync import TeamTools
from adv_archon.core.web_library import WebLibraryStore
from adv_archon.integrations.boe import tool_boe_fetch, tool_boe_search
from adv_archon.tools.browser import BrowserTools, build_browser_tool_specs
from adv_archon.tools.comparador import tool_comparar_parcelas
from adv_archon.tools.edificabilidad import tool_calcular_edificabilidad
from adv_archon.tools.google_workspace import (
    GoogleWorkspaceTools,
    build_google_workspace_tool_specs,
)
from adv_archon.tools.guarded_files import FileAccessPolicy, GuardedFileTools
from adv_archon.tools.knowledge_tools import KnowledgeTools, build_knowledge_tool_specs
from adv_archon.tools.mac import MacTools, build_mac_tool_specs
from adv_archon.tools.pem import tool_calcular_pem
from adv_archon.tools.personal import PersonalTools, build_personal_tool_specs
from adv_archon.tools.python_sandbox import PythonSandboxTool, build_python_tool_specs
from adv_archon.tools.shell import AutoModeManager, ShellPolicy, ShellTool, build_shell_tool_specs
from adv_archon.tools.task_tools import TaskTools, build_task_tool_specs
from adv_archon.tools.urban_compliance import UrbanComplianceTools
from adv_archon.tools.vision import VisionTools, build_vision_tool_specs
from adv_archon.tools.web import WebTools
from adv_archon.tools.web_library_tools import (
    WebLibraryTools,
    build_web_library_tool_specs,
)
from adv_archon.ui.commands import CommandServices
from adv_archon.ui.render import Renderer
from adv_archon.voice.stt import WhisperSpeechToText
from adv_archon.voice.tts import MacTextToSpeech

ConfirmCallback = Callable[[str], bool]
ProgressCallback = Callable[[int, str], None]


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
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        def _progress(pct: int, detail: str) -> None:
            if progress_callback is not None:
                progress_callback(pct, detail)

        self.config = config
        self.llm = llm
        self.project_root = project_root
        self.system_prompt = system_prompt
        self.incognito = incognito
        self.confirm = confirm

        _progress(5, "Iniciando sesión y registro…")
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

        _progress(18, "Configurando motor de lenguaje…")
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
        _progress(32, "Abriendo bases de datos de memoria y conocimiento…")
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
        from adv_archon.core.personal_kb import PersonalKB
        self.personal_kb = PersonalKB(config.paths.memory_db.parent / "personal_kb.db")
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
        _progress(50, "Cargando módulos urbanísticos y geográficos…")
        from adv_archon.core.geo_store import GeoStore
        from adv_archon.core.pgou_store import PGOUStore
        from adv_archon.core.scraper_daemon import ScraperDaemon
        from adv_archon.tools.geo_tools import GeoTools
        self.pgou_store = PGOUStore(config.paths.pgou_db, encoder=encoder)
        self.geo_store = GeoStore(config.paths.geo_db)
        self.geo_tools = GeoTools(self.geo_store, self.pgou_store)
        self.urban_compliance_tools = UrbanComplianceTools(
            self.pgou_store,
            llm,
            geo_tools=self.geo_tools,
        )
        self.compliance_tools = self.urban_compliance_tools
        # Background scraper daemon — keeps PGOU data fresh automatically
        self.scraper_daemon = ScraperDaemon(
            pgou_store=self.pgou_store,
            scraper=self.urban_compliance_tools._scraper,
            interval_hours=config.pgou.refresh_interval_hours
                if hasattr(config, "pgou") and hasattr(config.pgou, "refresh_interval_hours")
                else 24.0,
            max_age_days=30,
        )
        if not incognito:
            self.scraper_daemon.start()
        _progress(65, "Preparando tareas y herramientas personales…")
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
        _progress(75, "Iniciando navegador e integraciones…")
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
        # Nuevos tools: memoria descriptiva, PDF, PEM, informe integrado, equipo
        self.memoria_tools = MemoriaDescriptivaTools(llm, knowledge_store=self.knowledge_store)
        self.memoria_pdf_tools = MemoriaPDFTools(llm, knowledge_store=self.knowledge_store)
        self.informe_tools = InformeProyectoTools(llm, knowledge_store=self.knowledge_store)
        self.pem_pdf_tools = PEMPDFTools()
        self.team_tools = TeamTools(config)
        self.vision_tools = VisionTools(llm=llm)
        # ExpedienteStore se inyecta externamente (opcional — desktop lo hace)

        _progress(88, "Creando agente de IA…")
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
        _progress(97, "Finalizando configuración…")
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
        # Self-RAG: inject personal KB context when relevant
        try:
            kb_context = self.personal_kb.build_context_injection(prompt)
            if kb_context:
                enriched_prompt = kb_context + "\n\n" + enriched_prompt
        except Exception:
            pass  # KB errors must never break the main loop
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
            geo_tools=self.geo_tools,
            personal_kb=self.personal_kb,
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
            self.scraper_daemon.stop()
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
        if self.google_workspace_tools.is_configured():
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
        for definition in _build_geo_tool_specs(self.geo_tools):
            specs.append(
                ToolSpec(
                    name=definition["name"],
                    description=definition["description"],
                    schema=definition["schema"],
                    fn=definition["fn"],
                )
            )
        for definition in _build_boe_tool_specs():
            specs.append(ToolSpec(**definition))
        for definition in _build_edificabilidad_tool_specs():
            specs.append(ToolSpec(**definition))
        for definition in _build_comparador_tool_specs():
            specs.append(ToolSpec(**definition))
        for definition in _build_memoria_tool_specs(self.memoria_tools):
            specs.append(ToolSpec(**definition))
        for definition in _build_memoria_pdf_tool_specs(self.memoria_pdf_tools):
            specs.append(ToolSpec(**definition))
        for definition in _build_pem_tool_specs():
            specs.append(ToolSpec(**definition))
        for definition in _build_pem_pdf_tool_specs(self.pem_pdf_tools):
            specs.append(ToolSpec(**definition))
        for definition in _build_informe_tool_specs(self.informe_tools):
            specs.append(ToolSpec(**definition))
        for definition in _build_team_tool_specs(self.team_tools):
            specs.append(ToolSpec(**definition))
        for definition in build_vision_tool_specs(self.vision_tools):
            specs.append(ToolSpec(**definition))
        # Skills (Fase 2)
        import adv_archon.skills.code_patcher  # noqa: F401
        import adv_archon.skills.email_responder  # noqa: F401
        import adv_archon.skills.finance_briefing  # noqa: F401
        import adv_archon.skills.interview_prep  # noqa: F401
        import adv_archon.skills.readme_generator  # noqa: F401
        import adv_archon.skills.research  # noqa: F401
        from adv_archon.skills.registry import registry as _skill_registry

        for skill in _skill_registry.all():
            # Inject llm into skills that accept it
            if hasattr(skill, "_llm") and skill._llm is None:
                skill._llm = self.llm
        specs.extend(_skill_registry.to_tool_specs())
        return specs


def _build_memoria_pdf_tool_specs(tools: MemoriaPDFTools) -> list[dict[str, Any]]:
    return [
        {
            "name": "exportar_memoria_pdf",
            "description": (
                "Generate a complete Memoria Descriptiva and export it as a professional PDF "
                "with cover page, despacho branding, section headings, and legal disclaimer. "
                "Saves to the Desktop by default. Use this when the user asks for a PDF "
                "of the memoria or a document ready to deliver to the client."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "expediente_id": {
                        "type": "string",
                        "description": "UUID of the expediente.",
                    },
                    "despacho": {
                        "type": "string",
                        "description": "Name of the architecture firm to show in the header.",
                    },
                    "logo_path": {
                        "type": "string",
                        "description": "Optional path to a PNG/JPG logo file.",
                    },
                    "guardar_en": {
                        "type": "string",
                        "description": "Optional custom output path for the PDF.",
                    },
                },
                "required": ["expediente_id"],
            },
            "fn": tools.exportar_memoria_pdf,
        },
    ]


def _build_pem_tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "name": "calcular_pem",
            "description": (
                "Calculate the Presupuesto de Ejecución Material (PEM) for a building project "
                "using COA 2024 reference modules. Returns PEM, PEC (with overheads and fees), "
                "IVA, technical fees, and building permit cost (ICIO). "
                "Pure math — no LLM. Can export to CSV."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "superficie_construida_m2": {
                        "type": "number",
                        "description": "Total built area above ground in m².",
                    },
                    "tipologia": {
                        "type": "string",
                        "description": (
                            "Building type. Options: residencial_unifamiliar, "
                            "residencial_plurifamiliar, comercial, oficinas, industrial, "
                            "equipamiento, hotelero, rehabilitacion."
                        ),
                    },
                    "calidad": {
                        "type": "string",
                        "description": "Build quality: basica, media, alta, lujo.",
                    },
                    "zona": {
                        "type": "string",
                        "description": (
                            "Geographic zone affecting cost. Options: madrid, barcelona, "
                            "pais_vasco, navarra, baleares, canarias, cataluna, andalucia, "
                            "comunidad_valenciana, castilla_leon, castilla_mancha, galicia, "
                            "aragon, murcia, extremadura, asturias, cantabria, rioja, nacional."
                        ),
                    },
                    "num_plantas": {
                        "type": "integer",
                        "description": "Number of floors above ground.",
                    },
                    "superficie_sótano_m2": {
                        "type": "number",
                        "description": "Underground/basement area in m² (30% surcharge applied).",
                    },
                    "exportar_csv": {
                        "type": "boolean",
                        "description": "If true, saves a CSV breakdown to the Desktop.",
                    },
                    "csv_output_path": {
                        "type": "string",
                        "description": "Optional custom path for the CSV file.",
                    },
                },
                "required": ["superficie_construida_m2"],
            },
            "fn": tool_calcular_pem,
        },
    ]


def _extract_coordinate_pair_from_text(text: str) -> tuple[float, float] | None:
    match = re.search(
        r"(?P<lat>[+-]?\d{1,2}(?:\.\d+)?)[,\s]+(?P<lon>[+-]?\d{1,3}(?:\.\d+)?)",
        text,
    )
    if match is None:
        return None
    latitude = float(match.group("lat"))
    longitude = float(match.group("lon"))
    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        return None
    return latitude, longitude


def _maybe_build_compliance_prompt(
    prompt: str,
    attachments: Sequence[Path | str],
    compliance_tools: UrbanComplianceTools,
) -> str:
    """If the request looks like a plan compliance check, build a rich operator prompt."""

    pdf_paths = [
        str(path) for path in attachments if str(path).lower().endswith(".pdf")
    ]
    if not pdf_paths:
        return prompt

    if not looks_like_compliance_request(prompt):
        return prompt

    coordinate_pair = _extract_coordinate_pair_from_text(prompt)
    municipality = extract_municipality(prompt)
    plan_path = pdf_paths[0]

    if coordinate_pair is not None:
        latitude, longitude = coordinate_pair
        return (
            f"{prompt}\n\n"
            "INSTRUCCIÓN INTERNA: "
            "Flujo de análisis normativo por coordenadas activado automáticamente.\n"
            f"Coordenadas: ({latitude}, {longitude})\n"
            f"Plano PDF: {plan_path}\n\n"
            "Usa plan_compliance_check_by_coordinates con "
            f"plan_path='{plan_path}', latitude={latitude}, longitude={longitude} "
            "y auto_fetch=true. Después presenta el informe de cumplimiento de forma clara, "
            "con tabla de parámetros (altura, superficies, retranqueos, usos) indicando "
            "✓/⚠/✗ para cada uno."
        )

    if municipality is None:
        return (
            f"{prompt}\n\n"
            "INSTRUCCIÓN INTERNA: Se ha detectado un plano PDF y keywords de "
            "normativa urbanística. "
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

    wants_pdf = any(
        word in _normalize(prompt)
        for word in (
            "informe",
            "pdf",
            "exporta",
            "genera",
            "descarga",
            "report",
            "documento",
        )
    )

    tool_name = "plan_compliance_export" if wants_pdf else "plan_compliance_check"
    extra = (
        " El informe PDF se guardará en el Escritorio automáticamente."
        if wants_pdf
        else
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
    tools: UrbanComplianceTools,
) -> list[dict[str, Any]]:
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
            "name": "plan_compliance_check_by_coordinates",
            "description": (
                "Analyze an architectural plan PDF by first resolving GPS coordinates to the "
                "correct municipality, cadastral context, and PGOU status. If needed, it can "
                "auto-fetch the municipality normativa before running the compliance check."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "plan_path": {
                        "type": "string",
                        "description": "Absolute or ~ path to the architectural plan PDF.",
                    },
                    "latitude": {
                        "type": "number",
                        "description": "Decimal latitude of the plot.",
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Decimal longitude of the plot.",
                    },
                    "auto_fetch": {
                        "type": "boolean",
                        "description": (
                            "If true, auto-fetch missing PGOU normativa "
                            "before analysis."
                        ),
                    },
                },
                "required": ["plan_path", "latitude", "longitude"],
            },
            "fn": tools.plan_compliance_check_by_coordinates,
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
                "as a professional PDF report ready to share with clients or submit to "
                "the council. "
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


def _build_geo_tool_specs(tools: Any) -> list[dict[str, Any]]:
    return [
        {
            "name": "resolve_coordinates",
            "description": (
                "Resolve GPS coordinates (latitude, longitude) to a Spanish municipality, "
                "province, autonomous community, and cadastral reference. "
                "Use this when the user provides coordinates, a location pin, or asks "
                "'what can be built here / what is the PGOU for these coordinates'."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "latitude": {
                        "type": "number",
                        "description": "Decimal latitude (e.g. 40.4168 for Madrid).",
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Decimal longitude (e.g. -3.7038 for Madrid).",
                    },
                    "refresh": {
                        "type": "boolean",
                        "description": "Force a fresh lookup, ignoring the cache.",
                    },
                },
                "required": ["latitude", "longitude"],
            },
            "fn": tools.resolve_coordinates,
        },
        {
            "name": "site_compliance_context",
            "description": (
                "Full site context for a compliance check: resolves coordinates to a municipality, "
                "checks whether PGOU normativa is already indexed, and returns cadastral context "
                "plus a preliminary legal checklist for parcel-level review. Use this as the first "
                "tool when an architect provides coordinates for a plot."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                },
                "required": ["latitude", "longitude"],
            },
            "fn": tools.site_compliance_context,
        },
    ]


def _build_boe_tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "name": "boe_search",
            "description": (
                "Search the BOE (Boletín Oficial del Estado) for legislation, regulations, "
                "or official announcements in real time. Returns titles, dates, and identifiers."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query, e.g. 'Ley del Suelo urbanismo'.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default 5).",
                    },
                },
                "required": ["query"],
            },
            "fn": tool_boe_search,
        },
        {
            "name": "boe_fetch",
            "description": (
                "Fetch the full text of a BOE document by its identifier "
                "(e.g. 'BOE-A-2015-7164'). Returns the complete article text."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "identificador": {
                        "type": "string",
                        "description": "BOE document identifier, e.g. 'BOE-A-2015-7164'.",
                    },
                },
                "required": ["identificador"],
            },
            "fn": tool_boe_fetch,
        },
    ]


def _build_comparador_tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "name": "comparar_parcelas",
            "description": (
                "Compare 2 or 3 building plots side by side. For each plot, calculates "
                "maximum buildable area (techo edificable), plot coverage, PEM budget estimate, "
                "and CTE climate zone. Returns a comparative table and a recommendation. "
                "Use when the user wants to compare plots, choose between locations, or "
                "evaluate which site offers better development potential."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "parcelas": {
                        "type": "array",
                        "description": "List of 2-3 plots to compare.",
                        "minItems": 2,
                        "maxItems": 3,
                        "items": {
                            "type": "object",
                            "properties": {
                                "nombre": {"type": "string"},
                                "superficie_parcela_m2": {"type": "number"},
                                "coeficiente_edificabilidad": {"type": "number"},
                                "ocupacion_maxima_pct": {"type": "number"},
                                "num_plantas": {"type": "integer"},
                                "altura_maxima_m": {"type": "number"},
                                "tipologia": {"type": "string"},
                                "calidad": {"type": "string"},
                                "zona": {"type": "string"},
                                "municipio": {"type": "string"},
                                "provincia": {"type": "string"},
                            },
                            "required": [
                                "nombre",
                                "superficie_parcela_m2",
                                "coeficiente_edificabilidad",
                                "ocupacion_maxima_pct",
                                "num_plantas",
                                "altura_maxima_m",
                            ],
                        },
                    }
                },
                "required": ["parcelas"],
            },
            "fn": tool_comparar_parcelas,
        }
    ]


def _build_edificabilidad_tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "name": "calcular_edificabilidad",
            "description": (
                "Calculate buildable area parameters for a plot: maximum floor area (techo "
                "edificable), plot occupancy, floor-by-floor surface, maximum volume, free "
                "area, and setbacks. Pure math — no LLM involved. Can export results as CSV."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "superficie_parcela": {
                        "type": "number",
                        "description": "Plot area in m².",
                    },
                    "coef_edificabilidad": {
                        "type": "number",
                        "description": "Floor area ratio (e.g. 0.8 means 0.8 m²t/m²s).",
                    },
                    "ocupacion_max_pct": {
                        "type": "number",
                        "description": "Maximum plot coverage percentage (0–100).",
                    },
                    "altura_max_m": {
                        "type": "number",
                        "description": "Maximum building height in metres.",
                    },
                    "num_plantas": {
                        "type": "integer",
                        "description": "Number of floors above grade.",
                    },
                    "retranqueo_frontal_m": {
                        "type": "number",
                        "description": "Front setback in metres (default 0).",
                    },
                    "retranqueo_lateral_m": {
                        "type": "number",
                        "description": "Side setback in metres (default 0).",
                    },
                    "retranqueo_fondo_m": {
                        "type": "number",
                        "description": "Rear setback in metres (default 0).",
                    },
                    "exportar_csv": {
                        "type": "boolean",
                        "description": "If true, saves a CSV file to the Desktop.",
                    },
                    "csv_output_path": {
                        "type": "string",
                        "description": "Optional custom path for the CSV output file.",
                    },
                },
                "required": [
                    "superficie_parcela",
                    "coef_edificabilidad",
                    "ocupacion_max_pct",
                    "altura_max_m",
                    "num_plantas",
                ],
            },
            "fn": tool_calcular_edificabilidad,
        },
    ]


def _build_memoria_tool_specs(tools: MemoriaDescriptivaTools) -> list[dict[str, Any]]:
    return [
        {
            "name": "redactar_memoria",
            "description": (
                "Generate a complete professional Memoria Descriptiva for an expediente. "
                "Searches indexed PGOU normativa for the municipality, cites literal articles, "
                "and marks each requirement as CUMPLE / NO CUMPLE / PENDIENTE DE VERIFICAR. "
                "Saves the document to the Desktop by default."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "expediente_id": {
                        "type": "string",
                        "description": "UUID of the expediente to generate the memoria for.",
                    },
                    "guardar_en": {
                        "type": "string",
                        "description": "Optional custom output path (default: Desktop).",
                    },
                },
                "required": ["expediente_id"],
            },
            "fn": tools.redactar_memoria,
        },
    ]


def _build_pem_pdf_tool_specs(tools: PEMPDFTools) -> list[dict[str, Any]]:
    return [
        {
            "name": "exportar_pem_pdf",
            "description": (
                "Calculate PEM (Presupuesto de Ejecución Material) for a building project "
                "and export the full breakdown as a professional PDF with cover, data table, "
                "results table, and legal disclaimer. Saves to the Desktop by default. "
                "Use when the user asks for a PEM PDF, budget report, or presupuesto en PDF."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "superficie_construida_m2": {
                        "type": "number", "description": "Built area in m².",
                    },
                    "tipologia": {"type": "string", "description": "Building type."},
                    "calidad": {
                        "type": "string", "description": "Quality: basica, media, alta, lujo.",
                    },
                    "zona": {"type": "string", "description": "Geographic zone."},
                    "num_plantas": {"type": "integer"},
                    "superficie_sotano_m2": {"type": "number"},
                    "despacho": {"type": "string", "description": "Firm name for header."},
                    "guardar_en": {"type": "string", "description": "Optional output path."},
                },
                "required": ["superficie_construida_m2"],
            },
            "fn": tools.exportar_pem_pdf,
        }
    ]


def _build_informe_tool_specs(tools: InformeProyectoTools) -> list[dict[str, Any]]:
    return [
        {
            "name": "generar_informe_proyecto",
            "description": (
                "Generate a complete integrated project report as a single professional PDF. "
                "Combines edificabilidad analysis, PEM budget estimate, CTE energy pre-analysis, "
                "and the full memoria descriptiva in one document with cover page, "
                "Archon branding, and legal disclaimer. "
                "Use this when the user asks for a full project dossier or informe completo."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "expediente_id": {
                        "type": "string",
                        "description": "UUID of the expediente.",
                    },
                    "despacho": {
                        "type": "string",
                        "description": "Architecture firm name for the header.",
                    },
                    "logo_path": {
                        "type": "string",
                        "description": "Optional path to a PNG/JPG logo.",
                    },
                    "guardar_en": {
                        "type": "string",
                        "description": "Optional output path (default: Desktop).",
                    },
                    "incluir_pem": {
                        "type": "boolean",
                        "description": "Include PEM budget section (default: true).",
                    },
                    "incluir_energia": {
                        "type": "boolean",
                        "description": "Include CTE energy pre-analysis section (default: true).",
                    },
                    "incluir_memoria": {
                        "type": "boolean",
                        "description": "Include full memoria descriptiva section (default: true).",
                    },
                    "superficie_construida_m2": {
                        "type": "number",
                        "description": "Built area in m² for PEM calculation.",
                    },
                    "tipologia": {
                        "type": "string",
                        "description": "Building type for PEM (e.g. residencial_unifamiliar).",
                    },
                    "calidad": {
                        "type": "string",
                        "description": "Quality level for PEM: basica, media, alta, lujo.",
                    },
                },
                "required": ["expediente_id"],
            },
            "fn": tools.generar_informe_proyecto,
        },
    ]


def _build_team_tool_specs(tools: TeamTools) -> list[dict[str, Any]]:
    return [
        {
            "name": "exportar_expediente",
            "description": (
                "Export an expediente as a portable .archon file that can be shared with "
                "teammates and imported on any ADV ARCHON installation."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "expediente_id": {
                        "type": "string",
                        "description": "UUID of the expediente to export.",
                    },
                    "ruta_salida": {
                        "type": "string",
                        "description": "Optional output path (default: Desktop).",
                    },
                },
                "required": ["expediente_id"],
            },
            "fn": tools.exportar_expediente,
        },
        {
            "name": "importar_expediente",
            "description": (
                "Import a .archon file into the local expediente store. "
                "Use overwrite=true to replace an existing expediente with the same id."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "ruta_archivo": {
                        "type": "string",
                        "description": "Path to the .archon file to import.",
                    },
                    "sobreescribir": {
                        "type": "boolean",
                        "description": "If true, overwrite an existing expediente with the same id.",  # noqa: E501
                    },
                },
                "required": ["ruta_archivo"],
            },
            "fn": tools.importar_expediente,
        },
        {
            "name": "sincronizar_conocimiento",
            "description": (
                "Sync the local knowledge index with the team's shared folder "
                "(NAS, iCloud, Dropbox…). Pushes this user's knowledge.db and pulls "
                "knowledge chunks from all other team members."
            ),
            "schema": {"type": "object", "properties": {}, "required": []},
            "fn": tools.sincronizar_conocimiento,
        },
    ]
