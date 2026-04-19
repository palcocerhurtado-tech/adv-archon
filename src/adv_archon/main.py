from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from rich.console import Console

from adv_archon.core.config import load_app_config
from adv_archon.core.daily import build_daily_report
from adv_archon.core.llm import LLMRouter
from adv_archon.core.logging import AppLogger
from adv_archon.core.memory import MemoryStore, SentenceTransformerEncoder
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


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    config = load_app_config(mode_override=args.mode, system_prompt_override=args.system_prompt)
    llm = LLMRouter(config.llm)
    renderer = Renderer(Console())
    project_root = Path.cwd()

    if args.prompt == "daily" and not args.paths:
        session_id = datetime.now().strftime("daily-%Y%m%d%H%M%S")
        logger = AppLogger(config.paths.logs_dir, session_id=session_id, persist=not args.incognito)
        memory_store = MemoryStore(
            config.paths.memory_db,
            persist=not args.incognito,
            encoder=SentenceTransformerEncoder(config.memory.embedding_model),
            logger=logger,
        )
        report = build_daily_report(
            project_root=project_root,
            logs_dir=config.paths.logs_dir,
            memory_store=memory_store,
        )
        logger.log("daily_report_generated", project_root=project_root)
        renderer.show_info(report.render())
        return 0

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
