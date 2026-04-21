from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from rich.console import Console

from adv_archon.core.config import AppConfig, load_app_config
from adv_archon.core.daily import build_daily_report
from adv_archon.core.llm import LLMRouter
from adv_archon.core.logging import AppLogger
from adv_archon.core.memory import MemoryStore, SentenceTransformerEncoder
from adv_archon.core.tasks import TaskStore
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
