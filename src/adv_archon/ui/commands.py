from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from adv_archon.core.context import RuntimeContext
from adv_archon.core.costs import UsageLedger
from adv_archon.core.daily import DailyBrief, DailyReport, build_daily_brief, build_daily_report
from adv_archon.core.knowledge import KnowledgeStore
from adv_archon.core.llm import LLMRouter, ProviderMode
from adv_archon.core.logging import AppLogger
from adv_archon.core.memory import MemoryRecord, MemoryStore
from adv_archon.core.profiles import ProfileManager
from adv_archon.core.tasks import TaskStore
from adv_archon.tools.google_workspace import GoogleWorkspaceTools
from adv_archon.tools.graphify_tools import GraphifyTools, format_graphify_result
from adv_archon.tools.guarded_files import GuardedFileTools
from adv_archon.tools.knowledge_tools import KnowledgeTools
from adv_archon.tools.personal import PersonalTools
from adv_archon.tools.python_sandbox import PythonSandboxTool
from adv_archon.tools.shell import AutoModeManager, ShellTool, format_shell_result
from adv_archon.tools.web import WebTools
from adv_archon.ui.render import Renderer
from adv_archon.voice.stt import WhisperSpeechToText
from adv_archon.voice.tts import MacTextToSpeech


@dataclass(slots=True)
class CommandResult:
    handled: bool
    should_exit: bool = False
    injected_prompt: str | None = None


@dataclass(slots=True)
class CommandServices:
    llm: LLMRouter
    renderer: Renderer
    memory: MemoryStore
    task_store: TaskStore
    personal_tools: PersonalTools
    google_workspace_tools: GoogleWorkspaceTools
    knowledge_store: KnowledgeStore
    usage_ledger: UsageLedger
    logger: AppLogger
    context_provider: Callable[[], RuntimeContext]
    project_root: Path
    logs_dir: Path
    confirm: Callable[[str], bool]
    recall_limit: int
    incognito: bool
    auto_mode: AutoModeManager
    shell_tool: ShellTool
    python_tool: PythonSandboxTool
    knowledge_tools: KnowledgeTools
    file_tools: GuardedFileTools
    web_tools: WebTools
    profile_manager: ProfileManager
    on_profile_changed: Callable[[str], None]
    tts: MacTextToSpeech
    stt: WhisperSpeechToText
    graphify_tools: GraphifyTools


def handle_command(raw: str, *, services: CommandServices) -> CommandResult:
    if not raw.startswith("/"):
        return CommandResult(handled=False)

    command, _, argument = raw.partition(" ")
    argument = argument.strip()

    if command == "/help":
        services.renderer.show_help()
        return CommandResult(handled=True)

    if command == "/exit":
        return CommandResult(handled=True, should_exit=True)

    if command == "/daily":
        daily_mode = argument if argument else "brief"
        report: DailyBrief | DailyReport
        if daily_mode == "brief":
            report = build_daily_brief(
                project_root=services.project_root,
                logs_dir=services.logs_dir,
                memory_store=services.memory,
                task_store=services.task_store,
                personal_tools=services.personal_tools,
                google_tools=services.google_workspace_tools,
                knowledge_store=services.knowledge_store,
            )
            services.logger.log("slash_daily", mode="brief")
            services.renderer.show_info(report.render())
            return CommandResult(handled=True)
        if daily_mode == "raw":
            report = build_daily_report(
                project_root=services.project_root,
                logs_dir=services.logs_dir,
                memory_store=services.memory,
                task_store=services.task_store,
            )
            services.logger.log("slash_daily", mode="raw")
            services.renderer.show_info(report.render())
            return CommandResult(handled=True)
        services.renderer.show_error("Uso: /daily [brief|raw]")
        return CommandResult(handled=True)

    if command == "/briefing":
        prompt = (
            f"dame un briefing ejecutivo {argument}"
            if argument
            else "dame un briefing ejecutivo del día con agenda, inbox y prioridades"
        )
        services.logger.log("slash_briefing", prompt=prompt)
        return CommandResult(handled=True, injected_prompt=prompt)

    if command == "/mode":
        if argument not in {"cloud", "local"}:
            services.renderer.show_error("Uso: /mode <cloud|local>")
            return CommandResult(handled=True)
        services.llm.set_mode(cast(ProviderMode, argument))
        services.logger.log("mode_changed", mode=argument)
        services.renderer.show_info(f"Modo cambiado a {argument}.")
        return CommandResult(handled=True)

    if command == "/profile":
        if not argument or argument == "status":
            profile = services.profile_manager.describe()
            services.renderer.show_info(_format_profile(profile))
            return CommandResult(handled=True)
        profile_name = services.profile_manager.set_active_profile(argument)
        services.on_profile_changed(profile_name)
        services.logger.log("profile_changed", profile=profile_name)
        services.renderer.show_info(_format_profile(services.profile_manager.describe()))
        return CommandResult(handled=True)

    if command == "/auto":
        if not argument or argument == "status":
            services.renderer.show_info(f"AUTO: {services.auto_mode.status()}")
            return CommandResult(handled=True)
        if argument == "on":
            if services.auto_mode.enable(services.confirm):
                services.logger.log("auto_mode_changed", enabled=True)
                services.renderer.show_info("AUTO activado para esta sesión.")
            else:
                services.renderer.show_info("AUTO sigue desactivado.")
            return CommandResult(handled=True)
        if argument == "off":
            services.auto_mode.disable()
            services.logger.log("auto_mode_changed", enabled=False)
            services.renderer.show_info("AUTO desactivado.")
            return CommandResult(handled=True)
        services.renderer.show_error("Uso: /auto [on|off|status]")
        return CommandResult(handled=True)

    if command == "/voice":
        if not argument or argument == "status":
            services.renderer.show_info(f"Voz: {services.tts.describe()}")
            return CommandResult(handled=True)
        if argument == "on":
            services.tts.enable()
            services.logger.log("voice_toggled", enabled=True)
            services.renderer.show_info(f"Voz activada. {services.tts.describe()}")
            return CommandResult(handled=True)
        if argument == "off":
            services.tts.disable()
            services.logger.log("voice_toggled", enabled=False)
            services.renderer.show_info("Voz desactivada.")
            return CommandResult(handled=True)
        services.renderer.show_error("Uso: /voice [on|off|status]")
        return CommandResult(handled=True)

    if command == "/listen":
        services.renderer.show_info(f"Escuchando... {services.stt.describe()}")
        result = services.stt.listen_once()
        services.logger.log(
            "slash_listen",
            chars=len(result.text),
            duration_seconds=round(result.duration_seconds, 2),
        )
        services.renderer.show_info(f"Dictado: {result.text}")
        return CommandResult(handled=True, injected_prompt=result.text)

    if command == "/voice-note":
        title = argument or "Nota de voz ADV ARCHON"
        services.renderer.show_info(f"Escuchando nota de voz... {services.stt.describe()}")
        result = services.stt.listen_once()
        create_result = services.personal_tools.notes_create(
            title=title,
            body=result.text,
        )
        services.logger.log(
            "voice_note_created",
            title=title,
            chars=len(result.text),
            duration_seconds=round(result.duration_seconds, 2),
        )
        services.renderer.show_info(
            f"Nota de voz creada: {create_result.payload.get('title', title)}"
        )
        return CommandResult(handled=True)

    if command == "/read":
        if not argument:
            services.renderer.show_error("Uso: /read <path>")
            return CommandResult(handled=True)
        read_result = services.file_tools.read_file(argument)
        path = Path(read_result.payload["path"])
        services.logger.log("slash_read", path=str(path))
        services.renderer.show_info(f"{path}:\n{read_result.payload['content']}")
        return CommandResult(handled=True)

    if command == "/web":
        if not argument:
            services.renderer.show_error("Uso: /web <query>")
            return CommandResult(handled=True)
        web_result = services.web_tools.web_search(argument)
        services.logger.log(
            "slash_web_search",
            query=argument,
            results=len(web_result.payload["results"]),
        )
        lines = [
            f"- {item['title']} | {item['url']}\n  {item['snippet']}"
            for item in web_result.payload["results"]
        ]
        services.renderer.show_info("\n".join(lines) if lines else "Sin resultados.")
        return CommandResult(handled=True)

    if command == "/vault":
        if not argument:
            services.renderer.show_error("Uso: /vault <query>")
            return CommandResult(handled=True)
        vault_result = services.knowledge_tools.vault_search(argument, limit=5)
        services.logger.log(
            "slash_vault_search",
            query=argument,
            results=len(vault_result.payload["results"]),
            profile=vault_result.payload.get("profile"),
        )
        services.renderer.show_info(
            _format_knowledge_results(vault_result.payload, label="Vault")
        )
        return CommandResult(handled=True)

    if command == "/meeting":
        prompt = (
            f"prepárame la reunión {argument}" if argument else "prepárame la próxima reunión"
        )
        services.logger.log("slash_meeting", prompt=prompt)
        return CommandResult(handled=True, injected_prompt=prompt)

    if command == "/triage":
        prompt = (
            f"hazme triage del gmail sobre {argument}"
            if argument
            else "hazme triage del gmail y dime qué correos requieren respuesta"
        )
        services.logger.log("slash_triage", prompt=prompt)
        return CommandResult(handled=True, injected_prompt=prompt)

    if command == "/study":
        prompt = (
            f"actúa como study partner sobre {argument}"
            if argument
            else "actúa como study partner sobre el último documento que he abierto"
        )
        services.logger.log("slash_study", prompt=prompt)
        return CommandResult(handled=True, injected_prompt=prompt)

    if command == "/run":
        if not argument:
            services.renderer.show_error("Uso: /run <cmd>")
            return CommandResult(handled=True)
        shell_result = services.shell_tool.shell_exec(argument)
        services.renderer.show_info(format_shell_result(shell_result.payload))
        return CommandResult(handled=True)

    if command == "/python":
        if not argument:
            services.renderer.show_error("Uso: /python <code>")
            return CommandResult(handled=True)
        python_result = services.python_tool.python_exec(argument)
        services.renderer.show_info(
            format_shell_result(
                {
                    "command": "python -c ...",
                    "exit_code": python_result.payload["exit_code"],
                    "stdout": python_result.payload["stdout"],
                    "stderr": python_result.payload["stderr"],
                }
            )
        )
        return CommandResult(handled=True)

    if command == "/recall":
        if not argument:
            services.renderer.show_error("Uso: /recall <query>")
            return CommandResult(handled=True)
        records = services.memory.recall(argument, limit=services.recall_limit)
        services.logger.log("slash_recall", query=argument, results=len(records))
        if not records:
            services.renderer.show_info("No encuentro recuerdos relevantes.")
            return CommandResult(handled=True)
        services.renderer.show_info(_format_memory_records(records))
        return CommandResult(handled=True)

    if command == "/forget":
        if not argument:
            services.renderer.show_error("Uso: /forget <query|id>")
            return CommandResult(handled=True)
        if services.incognito:
            services.renderer.show_error(
                "En modo incógnito no se puede borrar memoria persistente."
            )
            return CommandResult(handled=True)
        candidates = services.memory.find_matches(argument, limit=services.recall_limit)
        if not candidates:
            services.renderer.show_info("No he encontrado recuerdos que coincidan.")
            return CommandResult(handled=True)
        services.renderer.show_info(_format_memory_records(candidates))
        question = f"¿Borro {len(candidates)} recuerdo(s)?"
        if not services.confirm(question):
            services.renderer.show_info("Cancelado.")
            return CommandResult(handled=True)
        deleted = services.memory.forget_by_ids([record.id for record in candidates])
        services.logger.log("slash_forget", query=argument, deleted=deleted)
        services.renderer.show_info(f"He borrado {deleted} recuerdo(s).")
        return CommandResult(handled=True)

    if command == "/cost":
        summary = services.usage_ledger.summary()
        events = services.usage_ledger.recent_events(limit=5)
        services.renderer.show_info(_format_cost_summary(summary, events))
        return CommandResult(handled=True)

    if command == "/log":
        limit = _parse_log_limit(argument)
        entries = services.logger.recent(limit=limit)
        if not entries:
            services.renderer.show_info("Todavía no hay eventos en esta sesión.")
            return CommandResult(handled=True)
        services.renderer.show_info(_format_log_entries(entries))
        return CommandResult(handled=True)

    if command == "/graphify":
        parts = argument.split(None, 1)
        subcommand = parts[0] if parts else "status"
        rest = parts[1] if len(parts) > 1 else ""

        if subcommand == "status":
            result = services.graphify_tools.graphify_status(rest or None)
            services.logger.log("slash_graphify_status", path=rest or ".")
            services.renderer.show_info(_format_graphify_status(result.payload))
            return CommandResult(handled=True)

        if subcommand == "run":
            services.renderer.show_info("Construyendo grafo Graphify…")
            result = services.graphify_tools.graphify_run(rest or None)
            services.logger.log(
                "slash_graphify_run",
                path=result.payload.get("project_path"),
                exit_code=result.payload.get("exit_code"),
            )
            services.renderer.show_info(format_graphify_result(result.payload))
            return CommandResult(handled=True)

        if subcommand == "update":
            services.renderer.show_info("Actualizando grafo Graphify…")
            result = services.graphify_tools.graphify_update(rest or None)
            services.logger.log(
                "slash_graphify_update",
                path=result.payload.get("project_path"),
                exit_code=result.payload.get("exit_code"),
            )
            services.renderer.show_info(format_graphify_result(result.payload))
            return CommandResult(handled=True)

        if subcommand == "query":
            if not rest:
                services.renderer.show_error("Uso: /graphify query <pregunta>")
                return CommandResult(handled=True)
            result = services.graphify_tools.graphify_query(rest)
            services.logger.log("slash_graphify_query", query=rest)
            services.renderer.show_info(format_graphify_result(result.payload))
            return CommandResult(handled=True)

        if subcommand == "path":
            tokens = rest.split(None, 1)
            if len(tokens) < 2:
                services.renderer.show_error("Uso: /graphify path <origen> <destino>")
                return CommandResult(handled=True)
            result = services.graphify_tools.graphify_path(tokens[0], tokens[1])
            services.logger.log("slash_graphify_path", source=tokens[0], target=tokens[1])
            services.renderer.show_info(format_graphify_result(result.payload))
            return CommandResult(handled=True)

        if subcommand == "explain":
            if not rest:
                services.renderer.show_error("Uso: /graphify explain <concepto>")
                return CommandResult(handled=True)
            result = services.graphify_tools.graphify_explain(rest)
            services.logger.log("slash_graphify_explain", concept=rest)
            services.renderer.show_info(format_graphify_result(result.payload))
            return CommandResult(handled=True)

        if subcommand == "add":
            if not rest:
                services.renderer.show_error("Uso: /graphify add <url>")
                return CommandResult(handled=True)
            result = services.graphify_tools.graphify_add(rest)
            services.logger.log("slash_graphify_add", url=rest)
            services.renderer.show_info(format_graphify_result(result.payload))
            return CommandResult(handled=True)

        services.renderer.show_error(
            "Uso: /graphify [status|run|update|query <q>|path <A> <B>|explain <c>|add <url>]"
        )
        return CommandResult(handled=True)

    services.renderer.show_error(f"Comando no reconocido: {command}")
    return CommandResult(handled=True)


def _format_memory_records(records: list[MemoryRecord]) -> str:
    lines = ["Memoria relevante:"]
    for record in records:
        tags = f" | tags: {', '.join(record.tags)}" if record.tags else ""
        score = f" | score: {record.score:.2f}" if record.score is not None else ""
        descriptor = f"{record.memory_type}/{record.namespace}"
        lines.append(f"- [#{record.id}] ({descriptor}) {record.content}{tags}{score}")
    return "\n".join(lines)


def _format_profile(profile: object) -> str:
    from adv_archon.core.profiles import ProfileDefinition

    active_profile = cast(ProfileDefinition, profile)
    lines = [
        f"Perfil activo: {active_profile.name}",
        active_profile.description,
    ]
    if active_profile.knowledge_roots:
        lines.append(f"Raices de conocimiento: {', '.join(active_profile.knowledge_roots)}")
    if active_profile.vault_roots:
        lines.append(f"Vaults Markdown: {', '.join(active_profile.vault_roots)}")
    return "\n".join(lines)


def _format_knowledge_results(payload: dict[str, object], *, label: str) -> str:
    raw_results = payload.get("results", [])
    profile = payload.get("profile")
    if not isinstance(raw_results, list) or not raw_results:
        prefix = f"{label} ({profile})" if profile else label
        return f"{prefix}: sin resultados."
    lines = [f"{label} ({profile or 'general'}):"]
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "sin titulo"))
        path = str(item.get("path", ""))
        excerpt = str(item.get("excerpt", "")).strip()
        lines.append(f"- {title} | {path}")
        if excerpt:
            lines.append(f"  {excerpt[:220]}")
    return "\n".join(lines)


def _format_cost_summary(summary: object, events: Sequence[object]) -> str:
    from adv_archon.core.costs import UsageEvent, UsageSummary

    usage_summary = cast(UsageSummary, summary)
    usage_events = cast(list[UsageEvent], events)
    breakdowns = usage_summary.breakdowns
    lines = [
        "Coste de la sesión:",
        f"- llamadas LLM: {usage_summary.total_calls}",
        f"- planner: {usage_summary.planner_calls}",
        f"- respuesta final: {usage_summary.assistant_calls}",
        f"- tokens prompt: {usage_summary.prompt_tokens}",
        f"- tokens salida: {usage_summary.completion_tokens}",
        f"- tokens totales: {usage_summary.total_tokens}",
        f"- coste estimado: ${usage_summary.estimated_cost_usd:.6f}",
        f"- llamadas con redacción PII: {usage_summary.redacted_calls}",
        f"- elementos PII redacted: {usage_summary.redacted_items}",
    ]
    if breakdowns:
        lines.append("Desglose:")
        for breakdown in breakdowns:
            lines.append(
                f"- {breakdown.provider}/{breakdown.model} | {breakdown.phase} | "
                f"{breakdown.calls} llamadas | {breakdown.total_tokens} tok | "
                f"${breakdown.estimated_cost_usd:.6f}"
            )
    if usage_events:
        lines.append("Últimas llamadas:")
        for event in usage_events:
            pii_label = " | pii" if event.redaction_applied else ""
            lines.append(
                f"- {event.phase} | {event.provider}/{event.model} | "
                f"{event.total_tokens} tok | ${event.estimated_cost_usd:.6f}{pii_label}"
            )
    return "\n".join(lines)


def _format_log_entries(entries: Sequence[object]) -> str:
    from adv_archon.core.logging import LogEntry

    log_entries = cast(list[LogEntry], entries)
    lines = ["Eventos recientes:"]
    for entry in log_entries:
        timestamp = entry.timestamp[11:19]
        if entry.fields:
            details = ", ".join(f"{key}={value}" for key, value in entry.fields.items())
            lines.append(f"- {timestamp} | {entry.event} | {details}")
        else:
            lines.append(f"- {timestamp} | {entry.event}")
    return "\n".join(lines)


def _parse_log_limit(argument: str) -> int:
    if not argument:
        return 10
    try:
        return max(1, int(argument))
    except ValueError:
        return 10


def _format_graphify_status(payload: dict[str, object]) -> str:
    installed = payload.get("graphify_installed", False)
    graph_exists = payload.get("graph_json_exists", False)
    project_path = payload.get("project_path", "")
    graph_dir = payload.get("graph_dir", "")
    size_bytes = int(payload.get("graph_json_size_bytes", 0))
    hint = payload.get("install_hint")
    lines = [
        f"Graphify instalado: {'sí' if installed else 'no'}",
        f"Proyecto: {project_path}",
        f"Grafo en: {graph_dir}",
        f"graph.json: {'✓' if graph_exists else '✗'}" + (f" ({size_bytes:,} bytes)" if graph_exists else ""),
    ]
    if hint:
        lines.append(f"Aviso: {hint}")
    if not graph_exists and installed:
        lines.append("Ejecuta /graphify run para construir el grafo.")
    return "\n".join(lines)
