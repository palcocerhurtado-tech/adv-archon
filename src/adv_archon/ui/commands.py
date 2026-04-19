from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from adv_archon.core.context import RuntimeContext
from adv_archon.core.costs import UsageLedger
from adv_archon.core.llm import LLMRouter, ProviderMode
from adv_archon.core.logging import AppLogger
from adv_archon.core.memory import MemoryRecord, MemoryStore
from adv_archon.tools.files import read_file
from adv_archon.tools.python_sandbox import PythonSandboxTool
from adv_archon.tools.shell import AutoModeManager, ShellTool, format_shell_result
from adv_archon.tools.web import web_search
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
    usage_ledger: UsageLedger
    logger: AppLogger
    context_provider: Callable[[], RuntimeContext]
    confirm: Callable[[str], bool]
    recall_limit: int
    incognito: bool
    auto_mode: AutoModeManager
    shell_tool: ShellTool
    python_tool: PythonSandboxTool
    tts: MacTextToSpeech
    stt: WhisperSpeechToText


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

    if command == "/mode":
        if argument not in {"cloud", "local"}:
            services.renderer.show_error("Uso: /mode <cloud|local>")
            return CommandResult(handled=True)
        services.llm.set_mode(cast(ProviderMode, argument))
        services.logger.log("mode_changed", mode=argument)
        services.renderer.show_info(f"Modo cambiado a {argument}.")
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

    if command == "/read":
        if not argument:
            services.renderer.show_error("Uso: /read <path>")
            return CommandResult(handled=True)
        read_result = read_file(argument)
        path = Path(read_result.payload["path"])
        services.logger.log("slash_read", path=str(path))
        services.renderer.show_info(f"{path}:\n{read_result.payload['content']}")
        return CommandResult(handled=True)

    if command == "/web":
        if not argument:
            services.renderer.show_error("Uso: /web <query>")
            return CommandResult(handled=True)
        web_result = web_search(argument)
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

    services.renderer.show_error(f"Comando no reconocido: {command}")
    return CommandResult(handled=True)


def _format_memory_records(records: list[MemoryRecord]) -> str:
    lines = ["Memoria relevante:"]
    for record in records:
        tags = f" | tags: {', '.join(record.tags)}" if record.tags else ""
        score = f" | score: {record.score:.2f}" if record.score is not None else ""
        lines.append(f"- [#{record.id}] {record.content}{tags}{score}")
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
