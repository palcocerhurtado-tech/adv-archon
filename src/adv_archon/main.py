from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

from rich.console import Console

from adv_archon.core.config import AppConfig, load_app_config
from adv_archon.core.daily import build_daily_report
from adv_archon.core.knowledge import KnowledgeStore, install_knowledge_launch_agent
from adv_archon.core.llm import LLMRouter
from adv_archon.core.logging import AppLogger
from adv_archon.core.memory import MemoryStore, SentenceTransformerEncoder
from adv_archon.core.research import install_research_launch_agent, run_research_cycle
from adv_archon.core.tasks import TaskStore
from adv_archon.core.web_library import WebLibraryStore
from adv_archon.ui.render import Renderer
from adv_archon.ui.repl import ReplApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adv-archon",
        description="ADV ARCHON terminal assistant",
    )
    parser.add_argument("prompt", nargs="?", help="One-shot prompt")
    parser.add_argument("paths", nargs="*", help="Optional file paths related to the prompt")
    parser.add_argument("--mode", choices=["cloud", "local"], help="Override the LLM provider mode")
    parser.add_argument("--auto", action="store_true", help="Enable AUTO mode after confirmation")
    parser.add_argument(
        "--listen",
        action="store_true",
        help="Capture one spoken prompt at startup; uses wake-word if configured.",
    )
    parser.add_argument(
        "--system-prompt",
        type=Path,
        help="Override the default system prompt path",
    )
    parser.add_argument(
        "--incognito",
        action="store_true",
        help="Do not persist sessions, memory writes, or logs",
    )
    return parser


def load_system_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _build_logger(config_root: Path, *, prefix: str, persist: bool) -> AppLogger:
    session_id = datetime.now().strftime(f"{prefix}-%Y%m%d%H%M%S")
    return AppLogger(config_root, session_id=session_id, persist=persist)


def _handle_daily(
    *,
    config: AppConfig,
    renderer: Renderer,
    project_root: Path,
    incognito: bool,
) -> int:
    logger = _build_logger(
        config.paths.logs_dir,
        prefix="daily",
        persist=not incognito,
    )
    memory_store = MemoryStore(
        config.paths.memory_db,
        persist=not incognito,
        encoder=SentenceTransformerEncoder(config.memory.embedding_model),
        logger=logger,
    )
    task_store = TaskStore(
        config.paths.tasks_db,
        timezone_name=config.tasks.default_timezone,
        notifications_enabled=config.tasks.notifications_enabled,
        logger=logger,
    )
    report = build_daily_report(
        project_root=project_root,
        logs_dir=config.paths.logs_dir,
        memory_store=memory_store,
        task_store=task_store,
    )
    logger.log("daily_report_generated", project_root=project_root)
    renderer.show_info(report.render())
    return 0


def _handle_tasks(
    *,
    config: AppConfig,
    renderer: Renderer,
    task_args: list[str],
) -> int:
    logger = _build_logger(config.paths.logs_dir, prefix="tasks", persist=True)
    store = TaskStore(
        config.paths.tasks_db,
        timezone_name=config.tasks.default_timezone,
        notifications_enabled=config.tasks.notifications_enabled,
        logger=logger,
    )
    command = task_args[0] if task_args else "list"
    if command == "run-due":
        records = store.run_due_tasks()
        if not records:
            renderer.show_info("No hay tareas vencidas.")
            return 0
        lines = ["Tareas disparadas:"]
        lines.extend(f"- [#{record.id}] {record.title} | {record.status}" for record in records)
        renderer.show_info("\n".join(lines))
        return 0
    if command == "list":
        status = task_args[1] if len(task_args) > 1 else None
        records = store.list_tasks(status=status, limit=20)
        if not records:
            renderer.show_info("No hay tareas persistentes.")
            return 0
        lines = ["Tareas persistentes:"]
        for record in records:
            recurrence = f" | recurrencia: {record.recurrence}" if record.recurrence else ""
            lines.append(
                f"- [#{record.id}] {record.title} | {record.status} | {record.due_at}{recurrence}"
            )
        renderer.show_info("\n".join(lines))
        return 0
    renderer.show_error("Uso: adv-archon tasks [list [open|all|done|due|cancelled]|run-due]")
    return 1


def _handle_knowledge(
    *,
    config: AppConfig,
    renderer: Renderer,
    knowledge_args: list[str],
    incognito: bool,
) -> int:
    logger = _build_logger(config.paths.logs_dir, prefix="knowledge", persist=not incognito)
    encoder = SentenceTransformerEncoder(config.memory.embedding_model)
    store = KnowledgeStore(
        config.paths.knowledge_db,
        encoder=encoder,
        default_roots=config.knowledge.default_roots,
        vault_roots=config.knowledge.vault_roots,
        auto_index_on_search=config.knowledge.auto_index_on_search,
        max_files_per_root=config.knowledge.max_files_per_root,
        max_file_bytes=config.knowledge.max_file_bytes,
        logger=logger,
    )
    command = knowledge_args[0] if knowledge_args else "status"
    if command == "status":
        roots = knowledge_args[1:] or None
        status = store.status(roots)
        last_scan_at = (
            status.last_run.finished_at
            if status.last_run and status.last_run.finished_at
            else (status.last_run.started_at if status.last_run else "nunca")
        )
        lines = [
            "Estado del conocimiento local:",
            f"- raices: {', '.join(status.roots) if status.roots else 'ninguna'}",
            f"- ficheros descubiertos: {status.discovered_files}",
            f"- ficheros indexados: {status.indexed_files}",
            f"- omitidos o sin indexar contenido: {status.skipped_files}",
            f"- pendientes: {status.pending_files}",
            f"- fallidos: {status.error_files}",
            f"- ultimo escaneo: {last_scan_at}",
        ]
        renderer.show_info("\n".join(lines))
        return 0
    if command == "index":
        roots = knowledge_args[1:] or list(config.knowledge.default_roots)
        result = store.index_paths(roots)
        renderer.show_info(_format_knowledge_index_result(result))
        return 0
    if command == "run-batch":
        batch_size = config.knowledge.background_batch_size
        roots_start = 1
        if len(knowledge_args) > 1 and knowledge_args[1].isdigit():
            batch_size = max(1, int(knowledge_args[1]))
            roots_start = 2
        roots = knowledge_args[roots_start:] or list(config.knowledge.default_roots)
        status = store.status(roots)
        if status.discovered_files == 0 or status.pending_files == 0:
            store.discover_paths(roots)
        result = store.ingest_pending_batch(roots, batch_size=batch_size)
        renderer.show_info(_format_knowledge_index_result(result))
        return 0
    if command == "search":
        query = " ".join(knowledge_args[1:]).strip()
        if not query:
            renderer.show_error("Uso: adv-archon knowledge search <query>")
            return 1
        records = store.search(query, limit=config.knowledge.search_limit)
        if not records:
            renderer.show_info("No encuentro conocimiento local relevante.")
            return 0
        lines = ["Resultados de conocimiento local:"]
        for record in records:
            suffix = f" | {record.status}" if record.status != "indexed" else ""
            lines.append(f"- {record.title} | {record.path}{suffix}")
            lines.append(f"  {record.excerpt}")
        renderer.show_info("\n".join(lines))
        return 0
    if command == "install-agent":
        adv_command = shutil.which("adv-archon") or shutil.which("adv")
        if adv_command is None:
            renderer.show_error("No encuentro `adv-archon` en PATH.")
            return 1
        roots = knowledge_args[1:] or list(config.knowledge.default_roots)
        plist_path = install_knowledge_launch_agent(
            adv_command=adv_command,
            interval_minutes=config.knowledge.background_interval_minutes,
            batch_size=config.knowledge.background_batch_size,
            roots=roots,
        )
        renderer.show_info(f"LaunchAgent de conocimiento instalado en {plist_path}")
        return 0
    renderer.show_error(
        "Uso: adv-archon knowledge "
        "[status [roots...]|index [roots...]|run-batch [batch] [roots...]|"
        "search <query>|install-agent [roots...]]"
    )
    return 1


def _handle_research(
    *,
    config: AppConfig,
    renderer: Renderer,
    research_args: list[str],
    incognito: bool,
) -> int:
    logger = _build_logger(config.paths.logs_dir, prefix="research", persist=not incognito)
    encoder = SentenceTransformerEncoder(config.memory.embedding_model)
    store = WebLibraryStore(
        config.paths.web_library_db,
        encoder=encoder,
        persist=not incognito,
        logger=logger,
    )
    command = research_args[0] if research_args else "status"
    if command == "status":
        fresh = store.search("", limit=5, include_stale=False)
        stale = store.search("", limit=50, include_stale=True)
        stale_count = len([record for record in stale if record.freshness_state == "stale"])
        lines = [
            "Estado de la biblioteca web local:",
            f"- entradas guardadas: {store.count()}",
            f"- frescas visibles: {len(fresh)}",
            f"- entradas potencialmente caducadas: {stale_count}",
            "- queries semilla: "
            + (
                ", ".join(config.research.seed_queries)
                if config.research.seed_queries
                else "ninguna"
            ),
        ]
        renderer.show_info("\n".join(lines))
        return 0
    if command == "search":
        query = " ".join(research_args[1:]).strip()
        if not query:
            renderer.show_error("Uso: adv-archon research search <query>")
            return 1
        records = store.search(query, limit=8)
        if not records:
            renderer.show_info("No encuentro fuentes guardadas en la biblioteca web.")
            return 0
        lines = ["Biblioteca web local:"]
        for record in records:
            lines.append(f"- {record.title} | {record.url} | {record.freshness_state}")
            lines.append(f"  {record.snippet}")
        renderer.show_info("\n".join(lines))
        return 0
    if command == "run-once":
        queries = research_args[1:] or list(config.research.seed_queries)
        if not queries:
            renderer.show_error(
                "No hay queries de investigación. "
                "Añádelas en [research].seed_queries o pásalas por CLI."
            )
            return 1
        result = run_research_cycle(
            store=store,
            queries=queries,
            search_results_per_query=config.research.search_results_per_query,
            fetch_top_results=config.research.fetch_top_results,
            logger=logger,
        )
        lines = [
            "Ciclo de investigación ejecutado:",
            f"- queries: {', '.join(result.queries)}",
            f"- resultados guardados/actualizados: {result.saved_results}",
            f"- URLs refrescadas: {result.refreshed_urls}",
            f"- fallos al refrescar: {result.failed_urls}",
        ]
        renderer.show_info("\n".join(lines))
        return 0
    if command == "install-agent":
        adv_command = shutil.which("adv-archon") or shutil.which("adv")
        if adv_command is None:
            renderer.show_error("No encuentro `adv-archon` en PATH.")
            return 1
        queries = research_args[1:] or list(config.research.seed_queries)
        if not queries:
            renderer.show_error(
                "No hay queries de investigación. "
                "Añádelas en [research].seed_queries o pásalas por CLI."
            )
            return 1
        plist_path = install_research_launch_agent(
            adv_command=adv_command,
            queries=queries,
            interval_minutes=config.research.launch_agent_interval_minutes,
        )
        renderer.show_info(f"LaunchAgent de research instalado en {plist_path}")
        return 0
    renderer.show_error(
        "Uso: adv-archon research "
        "[status|search <query>|run-once [queries...]|install-agent [queries...]]"
    )
    return 1


def _format_knowledge_index_result(result: object) -> str:
    from adv_archon.core.knowledge import KnowledgeIndexResult

    typed = result
    if not isinstance(typed, KnowledgeIndexResult):
        return str(result)
    lines = [
        "Indexación de conocimiento local:",
        f"- raices: {', '.join(typed.roots)}",
        f"- ficheros escaneados: {typed.scanned_files}",
        f"- ficheros indexados: {typed.indexed_files}",
        f"- sin cambios: {typed.unchanged_files}",
        f"- pendientes: {typed.pending_files}",
        f"- fallidos: {typed.failed_files}",
        f"- eliminados o ausentes: {typed.deleted_files}",
        f"- omitidos: {typed.skipped_files}",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    config = load_app_config(mode_override=args.mode, system_prompt_override=args.system_prompt)
    llm = LLMRouter(config.llm)
    renderer = Renderer(Console())
    project_root = Path.cwd()

    if args.prompt == "daily" and not args.paths:
        return _handle_daily(
            config=config,
            renderer=renderer,
            project_root=project_root,
            incognito=args.incognito,
        )

    if args.prompt == "tasks":
        return _handle_tasks(
            config=config,
            renderer=renderer,
            task_args=args.paths,
        )

    if args.prompt == "knowledge":
        return _handle_knowledge(
            config=config,
            renderer=renderer,
            knowledge_args=args.paths,
            incognito=args.incognito,
        )

    if args.prompt == "research":
        return _handle_research(
            config=config,
            renderer=renderer,
            research_args=args.paths,
            incognito=args.incognito,
        )

    system_prompt = load_system_prompt(config.system_prompt_path)

    app = ReplApp(
        config=config,
        llm=llm,
        project_root=project_root,
        system_prompt=system_prompt,
        renderer=renderer,
        incognito=args.incognito,
        auto_requested=args.auto,
        listen_requested=args.listen,
    )

    if args.prompt:
        prompt = args.prompt
        if args.paths:
            referenced = "\n".join(f"- {Path(path).expanduser()}" for path in args.paths)
            prompt = f"{prompt}\n\nReferenced paths:\n{referenced}\n\nOpen them if useful."
        return app.ask_once(prompt)

    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
