from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from adv_archon.core.context import RuntimeContext
from adv_archon.core.costs import UsageLedger
from adv_archon.core.daily import DailyBrief, DailyReport, build_daily_brief, build_daily_report
from adv_archon.core.knowledge import KnowledgeStore
from adv_archon.core.llm import LLMRouter, ProviderMode
from adv_archon.core.logging import AppLogger
from adv_archon.core.memory import MEMORY_CATEGORIES, MemoryRecord, MemoryStore
from adv_archon.core.profiles import ProfileManager
from adv_archon.core.tasks import TaskRecord, TaskStore
from adv_archon.tools.google_workspace import GoogleWorkspaceTools
from adv_archon.tools.guarded_files import GuardedFileTools
from adv_archon.tools.knowledge_tools import KnowledgeTools
from adv_archon.tools.personal import PersonalTools
from adv_archon.tools.python_sandbox import PythonSandboxTool
from adv_archon.tools.shell import AutoModeManager, ShellTool, format_shell_result
from adv_archon.tools.task_tools import TaskTools
from adv_archon.tools.urban_compliance import UrbanComplianceTools
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
    task_tools: TaskTools
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
    urban_compliance_tools: UrbanComplianceTools
    geo_tools: Any  # GeoTools — imported lazily to avoid circular
    personal_kb: Any = None  # PersonalKB — imported lazily to avoid heavy deps at startup


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

    if command == "/memory":
        return _handle_memory_command(argument, services=services)

    if command == "/automation":
        return _handle_automation_command(argument, services=services)

    if command == "/pgou":
        return _handle_pgou(argument, services=services)

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

    if command == "/live":
        return _handle_live_command(argument, services=services)

    if command == "/plan":
        if not argument:
            services.renderer.show_error("Uso: /plan <objetivo>")
            return CommandResult(handled=True)
        return _handle_plan_command(argument, services=services)

    if command == "/skills":
        from adv_archon.skills.registry import registry as _skill_registry
        skills = _skill_registry.all()
        if not skills:
            services.renderer.show_info("No hay skills registradas.")
        else:
            lines = ["Skills disponibles:"]
            for s in skills:
                lines.append(f"  • {s.name}: {s.description[:80]}")
            services.renderer.show_info("\n".join(lines))
        return CommandResult(handled=True)

    if command == "/kb":
        return _handle_kb_command(argument, services=services)

    services.renderer.show_error(f"Comando no reconocido: {command}")
    return CommandResult(handled=True)


def _format_memory_records(records: list[MemoryRecord]) -> str:
    lines = ["Memoria relevante:"]
    for record in records:
        tags = f" | tags: {', '.join(record.tags)}" if record.tags else ""
        score = f" | score: {record.score:.2f}" if record.score is not None else ""
        descriptor = (
            f"{record.memory_type}/{record.namespace}"
            f" | category: {record.category}"
            f" | importance: {record.importance}"
        )
        lines.append(f"- [#{record.id}] ({descriptor}) {record.content}{tags}{score}")
    return "\n".join(lines)


def _handle_live_command(argument: str, *, services: CommandServices) -> CommandResult:
    """Run a local voice loop using Whisper STT, Ollama and local TTS."""
    from adv_archon.core.llm_types import LLMMessage

    max_turns = 5
    if argument.strip():
        try:
            max_turns = max(1, min(20, int(argument.strip())))
        except ValueError:
            services.renderer.show_error("Uso: /live [número_de_turnos]")
            return CommandResult(handled=True)

    services.renderer.show_info(
        "Modo voz local iniciado. Usa Whisper local para escuchar, Ollama para "
        "responder y la voz del sistema si /voice está activo. Di 'salir' para terminar."
    )
    previous_mode = services.llm.mode
    services.llm.set_mode("local")
    history: list[LLMMessage] = []
    system_prompt = (
        "Eres ADV ARCHON en modo voz local. Responde breve, claro y útil. "
        "Prioriza arquitectura, expedientes, tareas y contexto local del usuario."
    )
    try:
        for _turn in range(max_turns):
            services.renderer.show_info(f"Escuchando... {services.stt.describe()}")
            heard = services.stt.listen_once()
            text = heard.text.strip()
            if not text:
                services.renderer.show_info("No he captado voz suficiente.")
                continue
            services.renderer.show_info(f"[Tú] {text}")
            if text.casefold() in {"salir", "adiós", "adios", "para", "cancelar"}:
                break
            history.append(LLMMessage(role="user", content=text))
            try:
                response = services.llm.complete(
                    history[-8:],
                    system_prompt=system_prompt,
                    task="assistant",
                    prefer_local=True,
                )
            except Exception as exc:
                services.renderer.show_error(f"No se pudo responder en modo local: {exc}")
                break
            answer = response.text.strip()
            history.append(LLMMessage(role="model", content=answer))
            services.renderer.show_info(f"[ARCHON] {answer}")
            if services.tts.is_enabled():
                services.tts.speak_async(answer)
    except KeyboardInterrupt:
        services.renderer.show_info("\nModo voz local interrumpido.")
    finally:
        services.llm.set_mode(previous_mode)
    services.renderer.show_info("Modo voz local finalizado.")
    return CommandResult(handled=True)


def _handle_plan_command(objective: str, *, services: CommandServices) -> CommandResult:
    """Generate a structured plan and ask the user for approval before executing."""
    from adv_archon.core.plan_schema import RiskLevel
    from adv_archon.core.planner import generate_plan

    services.renderer.show_info(f"Generando plan para: {objective} …")
    try:
        plan = generate_plan(objective, llm=services.llm)
    except Exception as exc:
        services.renderer.show_error(f"Error al generar el plan: {exc}")
        return CommandResult(handled=True)

    services.renderer.show_info(plan.summary())

    has_high = any(s.risk in (RiskLevel.HIGH, RiskLevel.CRITICAL) for s in plan.steps)
    if has_high:
        services.renderer.show_info(
            "\n⚠️  El plan contiene pasos de alto riesgo. Revisa antes de aprobar."
        )

    if not services.confirm("¿Apruebas este plan y quieres ejecutarlo?"):
        services.renderer.show_info("Plan cancelado.")
        return CommandResult(handled=True)

    plan.approved = True
    # Inject plan as a structured prompt so the agent executes it step by step
    steps_text = "\n".join(
        f"{s.index}. [{s.risk.value.upper()}] {s.intent} → {s.tool}({s.arguments})"
        for s in plan.steps
    )
    injected = (
        f"Ejecuta el siguiente plan aprobado paso a paso:\n\n"
        f"Objetivo: {plan.objective}\n\n"
        f"{steps_text}\n\n"
        "Confirma cada paso de alto riesgo antes de ejecutarlo."
    )
    return CommandResult(handled=True, injected_prompt=injected)


def _handle_kb_command(argument: str, *, services: CommandServices) -> CommandResult:
    """Handle /kb <subcommand> for the personal knowledge base."""
    kb = services.personal_kb
    subcommand, _, rest = argument.partition(" ")
    subcommand = subcommand.strip().lower()
    rest = rest.strip()

    if not subcommand or subcommand == "status":
        count = kb.count()
        services.renderer.show_info(
            f"Personal KB: {count} fragmento(s) indexado(s). "
            "Usa /kb index <ruta|url|texto> para añadir contenido."
        )
        return CommandResult(handled=True)

    if subcommand == "index":
        if not rest:
            services.renderer.show_error("Uso: /kb index <ruta|url|texto>")
            return CommandResult(handled=True)
        if rest.startswith("http://") or rest.startswith("https://"):
            services.renderer.show_info(f"Descargando e indexando: {rest} …")
            try:
                n = kb.add_url(rest)
                services.renderer.show_info(f"✓ {n} fragmento(s) añadido(s) desde URL.")
            except Exception as exc:
                services.renderer.show_error(f"Error indexando URL: {exc}")
        else:
            from pathlib import Path as _Path
            p = _Path(rest).expanduser()
            if p.is_file():
                services.renderer.show_info(f"Indexando archivo: {p} …")
                try:
                    n = kb.add_file(p)
                    services.renderer.show_info(f"✓ {n} fragmento(s) añadido(s).")
                except Exception as exc:
                    services.renderer.show_error(f"Error indexando archivo: {exc}")
            else:
                # Treat as raw text
                try:
                    kb.add(rest, source="texto_manual")
                    services.renderer.show_info("✓ Texto añadido a la KB.")
                except Exception as exc:
                    services.renderer.show_error(f"Error añadiendo texto: {exc}")
        return CommandResult(handled=True)

    if subcommand == "ask":
        if not rest:
            services.renderer.show_error("Uso: /kb ask <consulta>")
            return CommandResult(handled=True)
        results = kb.search(rest, limit=5)
        if not results:
            services.renderer.show_info("No he encontrado nada relevante en la KB.")
            return CommandResult(handled=True)
        lines = [f"Resultados en KB para: {rest}\n"]
        for i, rec in enumerate(results, 1):
            lines.append(
                f"[{i}] similitud={rec.score:.2f} | fuente={rec.source}\n"
                f"    {rec.preview(160)}\n"
            )
        services.renderer.show_info("\n".join(lines))
        return CommandResult(handled=True)

    if subcommand == "list":
        limit = int(rest) if rest.isdigit() else 10
        records = kb.list_all(limit=limit)
        if not records:
            services.renderer.show_info("La KB está vacía.")
            return CommandResult(handled=True)
        lines = [f"Últimos {len(records)} fragmento(s) en KB:"]
        for rec in records:
            lines.append(f"  [{rec.id[:8]}] {rec.source} — {rec.preview(100)}")
        services.renderer.show_info("\n".join(lines))
        return CommandResult(handled=True)

    if subcommand == "clear":
        if not services.confirm("¿Borrar toda la Personal KB?"):
            services.renderer.show_info("Cancelado.")
            return CommandResult(handled=True)
        n = kb.clear()
        services.renderer.show_info(f"✓ {n} fragmento(s) eliminado(s).")
        return CommandResult(handled=True)

    services.renderer.show_error(
        "Uso: /kb [status|index <ruta|url|texto>|ask <consulta>|list [n]|clear]"
    )
    return CommandResult(handled=True)


def _handle_memory_command(argument: str, *, services: CommandServices) -> CommandResult:
    if not argument or argument == "status":
        records = services.memory.list_memories(limit=8)
        services.renderer.show_info(_format_memory_overview(records))
        return CommandResult(handled=True)

    subcommand, _, remainder = argument.partition(" ")
    subcommand = subcommand.strip().lower()
    remainder = remainder.strip()

    if subcommand == "categories":
        services.renderer.show_info(
            "Categorías de memoria disponibles: " + ", ".join(sorted(MEMORY_CATEGORIES))
        )
        return CommandResult(handled=True)

    if subcommand == "list":
        category, query = _parse_memory_list_args(remainder)
        records = services.memory.list_memories(
            limit=12,
            category=None if category in {None, "all"} else category,
            query=query,
        )
        services.renderer.show_info(
            _format_memory_records(records) if records else "No encuentro recuerdos."
        )
        return CommandResult(handled=True)

    if subcommand == "remember":
        category, content = _parse_memory_remember_args(remainder)
        if not content:
            services.renderer.show_error("Uso: /memory remember <categoria> | <texto>")
            return CommandResult(handled=True)
        record = services.memory.remember(
            content,
            tags=[category, "manual"],
            source="slash-memory",
            memory_type="preference" if category in {"interests", "preferences"} else "fact",
            namespace="general",
            category=category,
            importance=4,
            metadata={"captured_from": "slash-memory"},
        )
        services.logger.log(
            "slash_memory_remember",
            memory_id=record.id,
            category=record.category,
            importance=record.importance,
        )
        services.renderer.show_info(
            f"He guardado [#{record.id}] en {record.category}: {record.content}"
        )
        return CommandResult(handled=True)

    if subcommand == "edit":
        memory_id, edit_content, options = _parse_memory_edit_args(remainder)
        if memory_id is None:
            services.renderer.show_error(
                "Uso: /memory edit <id> | <texto> | [category=...] | [importance=1-5]"
            )
            return CommandResult(handled=True)
        updated = services.memory.update_memory(
            memory_id,
            content=edit_content,
            category=cast(str | None, options.get("category")),
            importance=cast(int | None, options.get("importance")),
        )
        services.logger.log(
            "slash_memory_edit",
            memory_id=updated.id,
            category=updated.category,
            importance=updated.importance,
        )
        services.renderer.show_info(
            "He actualizado "
            f"[#{updated.id}] ({updated.category}, importancia {updated.importance})."
        )
        return CommandResult(handled=True)

    if subcommand == "forget":
        if not remainder:
            services.renderer.show_error("Uso: /memory forget <query|id>")
            return CommandResult(handled=True)
        candidates = services.memory.find_matches(remainder, limit=12)
        if not candidates:
            services.renderer.show_info("No he encontrado recuerdos que coincidan.")
            return CommandResult(handled=True)
        services.renderer.show_info(_format_memory_records(candidates))
        if not services.confirm(f"¿Borro {len(candidates)} recuerdo(s)?"):
            services.renderer.show_info("Cancelado.")
            return CommandResult(handled=True)
        deleted = services.memory.forget_by_ids([record.id for record in candidates])
        services.logger.log("slash_memory_forget", query=remainder, deleted=deleted)
        services.renderer.show_info(f"He borrado {deleted} recuerdo(s).")
        return CommandResult(handled=True)

    services.renderer.show_error(
        "Uso: /memory [status|categories|list [categoria|all] [query]|"
        "remember <categoria> | <texto>|edit <id> | <texto> | "
        "[category=...] | [importance=1-5]|forget <query|id>]"
    )
    return CommandResult(handled=True)


def _handle_automation_command(argument: str, *, services: CommandServices) -> CommandResult:
    if not argument or argument == "status":
        presets = services.task_tools.task_list_automation_presets().payload["presets"]
        tasks = services.task_store.list_tasks(limit=20)
        services.renderer.show_info(_format_automation_status(presets, tasks))
        return CommandResult(handled=True)

    subcommand, _, remainder = argument.partition(" ")
    subcommand = subcommand.strip().lower()
    remainder = remainder.strip()

    if subcommand == "presets":
        presets = services.task_tools.task_list_automation_presets().payload["presets"]
        services.renderer.show_info(_format_automation_status(presets, []))
        return CommandResult(handled=True)

    if subcommand == "install":
        result = services.task_tools.task_install_executive_automation(
            study_focus=remainder or "tu linea actual de estudio"
        )
        services.logger.log(
            "slash_automation_install",
            launch_agents=len(result.payload.get("launch_agents", [])),
            tasks=len(result.payload.get("tasks", [])),
        )
        services.renderer.show_info(_format_automation_install_result(result.payload))
        return CommandResult(handled=True)

    if subcommand == "tasks":
        tasks = services.task_store.list_tasks(limit=20)
        services.renderer.show_info(_format_automation_tasks(tasks))
        return CommandResult(handled=True)

    services.renderer.show_error("Uso: /automation [status|presets|install [foco]|tasks]")
    return CommandResult(handled=True)


def _handle_pgou(argument: str, *, services: CommandServices) -> CommandResult:
    subcommand, _, remainder = argument.partition(" ")
    subcommand = subcommand.strip().lower()
    remainder = remainder.strip()

    if not subcommand or subcommand == "status":
        result = services.urban_compliance_tools.pgou_status()
        payload = result.payload
        munis = payload.get("municipalities", [])
        if not munis:
            services.renderer.show_info(
                "No hay normativa indexada todavía.\n"
                "Usa /pgou add <municipio> para indexar un PGOU.\n"
                "Ejemplo: /pgou add Madrid"
            )
        else:
            lines = [f"Municipios indexados ({payload['total']}):"]
            for m in munis:
                lines.append(
                    f"  - {m['name']} | {m['chunks']} fragmentos | "
                    f"indexado {m['indexed_at'][:10]}"
                )
            services.renderer.show_info("\n".join(lines))
        return CommandResult(handled=True)

    if subcommand == "locate":
        if not remainder:
            services.renderer.show_error(
                "Uso: /pgou locate <lat> <lon>\n"
                "Ejemplo: /pgou locate 40.4168 -3.7038"
            )
            return CommandResult(handled=True)
        parts = remainder.split()
        if len(parts) < 2:
            services.renderer.show_error(
                "Necesito latitud y longitud.\n"
                "Ejemplo: /pgou locate 40.4168 -3.7038"
            )
            return CommandResult(handled=True)
        try:
            lat, lon = float(parts[0]), float(parts[1])
        except ValueError:
            services.renderer.show_error("Latitud y longitud deben ser números decimales.")
            return CommandResult(handled=True)
        prompt = (
            f"Resuelve las coordenadas GPS ({lat}, {lon}) para determinar "
            "en qué municipio español se encuentran y qué normativa urbanística (PGOU) aplica. "
            "Usa la herramienta site_compliance_context con esas coordenadas. "
            "Luego explica el municipio, provincia, referencia catastral si está disponible, "
            "si el PGOU ya está indexado o hay que descargarlo primero, y qué advertencias "
            "sectoriales o comprobaciones jurídicas siguen pendientes sobre la parcela."
        )
        services.logger.log("slash_pgou_locate", lat=lat, lon=lon)
        return CommandResult(handled=True, injected_prompt=prompt)

    if subcommand == "add":
        if not remainder:
            services.renderer.show_error(
                "Uso: /pgou add <municipio>\n"
                "Proporciona el nombre del municipio. ARCHON buscará y descargará "
                "la normativa urbanística automáticamente."
            )
            return CommandResult(handled=True)
        prompt = (
            f"Necesito indexar la normativa urbanística (PGOU o normas urbanísticas) "
            f"del municipio de {remainder} en España. "
            f"Busca el texto oficial en la web, descárgalo y luego usa la herramienta "
            f"pgou_add para indexarlo con municipality='{remainder}'. "
            f"Si no encuentras el PGOU completo, indexa al menos las normas urbanísticas "
            f"o el resumen de parámetros edificatorios que encuentres."
        )
        services.logger.log("slash_pgou_add", municipality=remainder)
        return CommandResult(handled=True, injected_prompt=prompt)

    if subcommand == "check":
        if not remainder:
            services.renderer.show_error(
                "Uso: /pgou check <ruta_plano.pdf> [municipio]\n"
                "Ejemplo: /pgou check ~/Desktop/plano.pdf Madrid"
            )
            return CommandResult(handled=True)
        parts = remainder.rsplit(" ", 1)
        plan_path = parts[0].strip()
        municipality = parts[1].strip() if len(parts) > 1 else ""
        if not municipality:
            services.renderer.show_error(
                "Especifica también el municipio.\n"
                "Ejemplo: /pgou check ~/Desktop/plano.pdf Madrid"
            )
            return CommandResult(handled=True)
        prompt = (
            f"Analiza el plano arquitectónico en '{plan_path}' "
            f"contra la normativa urbanística del municipio de {municipality}. "
            f"Usa la herramienta plan_compliance_check con "
            f"plan_path='{plan_path}' y municipality='{municipality}'. "
            f"Luego presenta el informe de forma clara y ordenada."
        )
        services.logger.log("slash_pgou_check", plan_path=plan_path, municipality=municipality)
        return CommandResult(handled=True, injected_prompt=prompt)

    if subcommand == "check-coords":
        if not remainder:
            services.renderer.show_error(
                "Uso: /pgou check-coords <lat> <lon> <ruta_plano.pdf>\n"
                "Ejemplo: /pgou check-coords 40.4168 -3.7038 ~/Desktop/plano.pdf"
            )
            return CommandResult(handled=True)
        parts = remainder.split(maxsplit=2)
        if len(parts) < 3:
            services.renderer.show_error(
                "Necesito latitud, longitud y ruta del plano PDF.\n"
                "Ejemplo: /pgou check-coords 40.4168 -3.7038 ~/Desktop/plano.pdf"
            )
            return CommandResult(handled=True)
        try:
            lat = float(parts[0])
            lon = float(parts[1])
        except ValueError:
            services.renderer.show_error("Latitud y longitud deben ser números decimales.")
            return CommandResult(handled=True)
        plan_path = parts[2].strip()
        if not plan_path:
            services.renderer.show_error("Indica también la ruta del plano PDF.")
            return CommandResult(handled=True)
        prompt = (
            f"Analiza el plano arquitectónico en '{plan_path}' "
            f"a partir de las coordenadas GPS ({lat}, {lon}). "
            "Usa la herramienta plan_compliance_check_by_coordinates con "
            f"plan_path='{plan_path}', latitude={lat}, longitude={lon} y auto_fetch=true. "
            "Si la normativa no está indexada pero existe en catálogo, descárgala primero "
            "automáticamente y luego presenta el informe de forma clara y ordenada."
        )
        services.logger.log("slash_pgou_check_coords", plan_path=plan_path, lat=lat, lon=lon)
        return CommandResult(handled=True, injected_prompt=prompt)

    if subcommand == "report":
        if not remainder:
            services.renderer.show_error(
                "Uso: /pgou report <ruta_plano.pdf> <municipio>\n"
                "Ejemplo: /pgou report ~/Desktop/plano.pdf Madrid\n"
                "Genera el análisis y exporta un PDF al Escritorio."
            )
            return CommandResult(handled=True)
        parts = remainder.rsplit(" ", 1)
        plan_path = parts[0].strip()
        municipality = parts[1].strip() if len(parts) > 1 else ""
        if not municipality:
            services.renderer.show_error(
                "Especifica también el municipio.\n"
                "Ejemplo: /pgou report ~/Desktop/plano.pdf Madrid"
            )
            return CommandResult(handled=True)
        prompt = (
            f"Analiza el plano arquitectónico en '{plan_path}' contra la normativa "
            f"de {municipality} y exporta el informe como PDF. "
            f"Usa la herramienta plan_compliance_export con "
            f"plan_path='{plan_path}' y municipality='{municipality}'. "
            "Cuando termine, dime la ruta del PDF generado."
        )
        services.logger.log("slash_pgou_report", plan_path=plan_path, municipality=municipality)
        return CommandResult(handled=True, injected_prompt=prompt)

    if subcommand == "fetch":
        if not remainder or remainder == "--all":
            # Fetch all catalogued municipalities
            prompt = (
                "Descarga e indexa automáticamente la normativa urbanística (PGOU) de todos "
                "los municipios disponibles en el catálogo. "
                "Usa la herramienta pgou_fetch_all con skip_indexed=true para saltar los que "
                "ya estén indexados. Informa del progreso y del resultado final."
            )
            services.logger.log("slash_pgou_fetch_all")
            return CommandResult(handled=True, injected_prompt=prompt)

        # Fetch a specific municipality
        prompt = (
            f"Descarga e indexa automáticamente la normativa urbanística (PGOU) del municipio "
            f"de {remainder} desde su fuente oficial. "
            f"Usa la herramienta pgou_fetch con municipality='{remainder}'. "
            f"Informa del resultado: cuántos fragmentos se indexaron y desde qué URL."
        )
        services.logger.log("slash_pgou_fetch", municipality=remainder)
        return CommandResult(handled=True, injected_prompt=prompt)

    if subcommand == "catalogue":
        result = services.urban_compliance_tools.pgou_catalogue()
        payload = result.payload
        entries = payload.get("municipalities", [])
        total = payload.get("total", 0)
        indexed = payload.get("indexed", 0)
        lines = [f"Catálogo PGOU ({indexed}/{total} indexados):"]
        for e in entries:
            marker = "[OK]" if e["indexed"] else "[ ]"
            lines.append(f"  {marker} {e['name']} ({e['kind']})")
        services.renderer.show_info("\n".join(lines))
        return CommandResult(handled=True)

    if subcommand == "delete":
        if not remainder:
            services.renderer.show_error("Uso: /pgou delete <municipio>")
            return CommandResult(handled=True)
        deleted = services.urban_compliance_tools._store.delete_municipality(remainder)
        if deleted:
            services.renderer.show_info(f"Normativa de '{remainder}' eliminada.")
        else:
            services.renderer.show_error(f"No se encontró normativa indexada para '{remainder}'.")
        return CommandResult(handled=True)

    services.renderer.show_error(
        "Uso: /pgou [status | catalogue | locate <lat> <lon> | "
        "fetch [<municipio>|--all] | add <municipio> | "
        "check <plano.pdf> <municipio> | report <plano.pdf> <municipio> | "
        "delete <municipio>]"
    )
    return CommandResult(handled=True)


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


def _parse_memory_list_args(argument: str) -> tuple[str | None, str | None]:
    if not argument:
        return None, None
    head, _, tail = argument.partition(" ")
    category = head.strip().lower()
    if category in MEMORY_CATEGORIES or category == "all":
        return category, tail.strip() or None
    return None, argument.strip()


def _parse_memory_remember_args(argument: str) -> tuple[str, str]:
    if "|" not in argument:
        return "general", argument.strip()
    category, _, content = argument.partition("|")
    normalized = category.strip().lower() or "general"
    if normalized not in MEMORY_CATEGORIES:
        normalized = "general"
    return normalized, content.strip()


def _parse_memory_edit_args(
    argument: str,
) -> tuple[int | None, str | None, dict[str, object]]:
    if not argument:
        return None, None, {}
    parts = [part.strip() for part in argument.split("|") if part.strip()]
    if not parts:
        return None, None, {}
    try:
        memory_id = int(parts[0].split()[0])
    except ValueError:
        return None, None, {}
    content: str | None = None
    options: dict[str, object] = {}
    for part in parts[1:]:
        if "=" in part:
            key, _, value = part.partition("=")
            key = key.strip().lower()
            value = value.strip()
            if key == "category" and value in MEMORY_CATEGORIES:
                options["category"] = value
            elif key == "importance":
                try:
                    options["importance"] = max(1, min(5, int(value)))
                except ValueError:
                    continue
            continue
        if content is None:
            content = str(part)
    return memory_id, content, options


def _format_memory_overview(records: list[MemoryRecord]) -> str:
    if not records:
        return "No tengo memoria persistente visible ahora mismo."
    counts: dict[str, int] = {category: 0 for category in sorted(MEMORY_CATEGORIES)}
    for record in records:
        counts[record.category] = counts.get(record.category, 0) + 1
    lines = ["Estado de memoria:"]
    lines.extend(f"- {category}: {count}" for category, count in counts.items() if count)
    lines.append("Recuerdos destacados:")
    for record in records[:5]:
        lines.append(
            f"- [#{record.id}] ({record.category}, imp {record.importance}) {record.content}"
        )
    return "\n".join(lines)


def _format_automation_status(
    presets: object,
    tasks: Sequence[TaskRecord],
) -> str:
    lines = ["Automatización ejecutiva:"]
    if isinstance(presets, list) and presets:
        preset = presets[0]
        if isinstance(preset, dict):
            lines.append(f"- preset: {preset.get('name', 'Executive Assistant')}")
            description = str(preset.get("description", "")).strip()
            if description:
                lines.append(description)
            workflows = preset.get("launch_workflows", [])
            if isinstance(workflows, list):
                lines.append("Workflows:")
                for workflow in workflows:
                    if not isinstance(workflow, dict):
                        continue
                    title = str(workflow.get("title", workflow.get("key", "workflow")))
                    times = workflow.get("times") or []
                    interval = workflow.get("interval_minutes")
                    if times:
                        lines.append(f"- {title} | {', '.join(str(item) for item in times)}")
                    elif interval:
                        lines.append(f"- {title} | cada {interval} min")
    automation_tasks = [
        task
        for task in tasks
        if getattr(task, "source", None)
        and "automation:" in str(getattr(task, "source", ""))
    ]
    if automation_tasks:
        lines.append("Tareas persistentes instaladas:")
        for task in automation_tasks[:8]:
            lines.append(
                f"- [#{task.id}] {task.title} | {task.due_at} | {task.category or 'general'}"
            )
    else:
        lines.append("- No detecto tareas de automatización instaladas todavía.")
    return "\n".join(lines)


def _format_automation_install_result(payload: dict[str, object]) -> str:
    lines = [
        "Automatización ejecutiva instalada.",
        f"- bundle: {payload.get('bundle', 'executive_assistant')}",
    ]
    launch_agents = payload.get("launch_agents", [])
    if isinstance(launch_agents, list):
        lines.append(f"- launch agents: {len(launch_agents)}")
        for item in launch_agents[:4]:
            if isinstance(item, dict):
                lines.append(f"  {item.get('label')} | {item.get('plist_path')}")
    tasks = payload.get("tasks", [])
    if isinstance(tasks, list):
        lines.append(f"- tareas persistentes: {len(tasks)}")
        for item in tasks[:4]:
            if isinstance(item, dict):
                lines.append(f"  {item.get('title')} | {item.get('due_at')}")
    return "\n".join(lines)


def _format_automation_tasks(tasks: Sequence[TaskRecord]) -> str:
    automation_tasks = [
        task
        for task in tasks
        if getattr(task, "source", None)
        and "automation:" in str(getattr(task, "source", ""))
    ]
    if not automation_tasks:
        return "No detecto tareas persistentes de automatización."
    lines = ["Tareas de automatización:"]
    for task in automation_tasks:
        lines.append(
            f"- [#{task.id}] {task.title} | {task.status} | {task.due_at} | "
            f"{task.category or 'general'}"
        )
    return "\n".join(lines)
