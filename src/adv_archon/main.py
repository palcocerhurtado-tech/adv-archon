from __future__ import annotations

import argparse
import io
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast


def Console(*args: Any, **kwargs: Any) -> Any:
    from rich.console import Console as _Console

    return _Console(*args, **kwargs)


def Renderer(*args: Any, **kwargs: Any) -> Any:
    from adv_archon.ui.render import Renderer as _Renderer

    return _Renderer(*args, **kwargs)


def LLMRouter(*args: Any, **kwargs: Any) -> Any:
    from adv_archon.core.llm import LLMRouter as _LLMRouter

    return _LLMRouter(*args, **kwargs)


def ReplApp(*args: Any, **kwargs: Any) -> Any:
    from adv_archon.ui.repl import ReplApp as _ReplApp

    return _ReplApp(*args, **kwargs)


def load_app_config(*args: Any, **kwargs: Any) -> Any:
    from adv_archon.core.config import load_app_config as _load_app_config

    return _load_app_config(*args, **kwargs)


def launch_desktop_app(*args: Any, **kwargs: Any) -> int:
    from adv_archon.desktop.app import launch_desktop_app as _launch_desktop_app

    return _launch_desktop_app(*args, **kwargs)


def create_macos_app_bundle(*args: Any, **kwargs: Any) -> Any:
    from adv_archon.desktop.bundle import create_macos_app_bundle as _create_bundle

    return _create_bundle(*args, **kwargs)


def format_prompt_with_attachments(*args: Any, **kwargs: Any) -> str:
    from adv_archon.core.attachments import (
        format_prompt_with_attachments as _format_prompt_with_attachments,
    )

    return _format_prompt_with_attachments(*args, **kwargs)


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


def desktop_main() -> int:
    config = load_app_config()
    llm = LLMRouter(config.llm)
    project_root = Path.cwd()
    system_prompt = load_system_prompt(config.system_prompt_path)
    return launch_desktop_app(
        config=config,
        llm=llm,
        project_root=project_root,
        system_prompt=system_prompt,
        incognito=False,
    )


def _handle_desktop_bundle(
    *,
    renderer: Any,
    bundle_args: list[str],
) -> int:
    destination_dir = (
        Path(bundle_args[0]).expanduser() if bundle_args else Path.home() / "Applications"
    )
    result = create_macos_app_bundle(destination_dir=destination_dir)
    renderer.show_info(
        "Bundle desktop creado.\n"
        f"- app: {result.app_path}\n"
        f"- launcher: {result.launcher_path}"
    )
    return 0


def _build_logger(config_root: Path, *, prefix: str, persist: bool) -> Any:
    from adv_archon.core.logging import AppLogger

    session_id = datetime.now().strftime(f"{prefix}-%Y%m%d%H%M%S")
    return AppLogger(config_root, session_id=session_id, persist=persist)


def _handle_daily(
    *,
    config: Any,
    renderer: Any,
    project_root: Path,
    incognito: bool,
    daily_args: list[str],
) -> int:
    from adv_archon.core.daily import build_daily_brief, build_daily_report
    from adv_archon.core.knowledge import KnowledgeStore
    from adv_archon.core.memory import MemoryStore, SentenceTransformerEncoder
    from adv_archon.core.tasks import TaskStore
    from adv_archon.tools.google_workspace import GoogleWorkspaceTools
    from adv_archon.tools.personal import PersonalTools

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
    encoder = SentenceTransformerEncoder(config.memory.embedding_model)
    knowledge_store = KnowledgeStore(
        config.paths.knowledge_db,
        encoder=encoder,
        default_roots=config.knowledge.default_roots,
        vault_roots=config.knowledge.vault_roots,
        auto_index_on_search=config.knowledge.auto_index_on_search,
        max_files_per_root=config.knowledge.max_files_per_root,
        max_file_bytes=config.knowledge.max_file_bytes,
        logger=logger,
    )
    personal_tools = PersonalTools(
        confirm=lambda _question: False,
        timezone_name=config.tasks.default_timezone,
        logger=logger,
    )
    google_tools = GoogleWorkspaceTools(
        client_secret_file=config.google.client_secret_file,
        token_file=config.google.token_file,
        confirm=lambda _question: False,
        enabled=config.google.enabled,
        timezone_name=config.tasks.default_timezone,
        default_calendar_id=config.google.default_calendar_id,
        gmail_default_max_results=config.google.gmail_default_max_results,
        drive_default_max_results=config.google.drive_default_max_results,
        logger=logger,
    )
    command = daily_args[0] if daily_args else "brief"
    report: Any
    if command == "raw":
        report = build_daily_report(
            project_root=project_root,
            logs_dir=config.paths.logs_dir,
            memory_store=memory_store,
            task_store=task_store,
        )
        logger.log("daily_report_generated", project_root=project_root, mode="raw")
    elif command == "brief":
        report = build_daily_brief(
            project_root=project_root,
            logs_dir=config.paths.logs_dir,
            memory_store=memory_store,
            task_store=task_store,
            personal_tools=personal_tools,
            google_tools=google_tools,
            knowledge_store=knowledge_store,
        )
        logger.log("daily_report_generated", project_root=project_root, mode="brief")
    else:
        renderer.show_error("Uso: adv-archon daily [brief|raw]")
        return 1
    renderer.show_info(report.render())
    return 0


def _handle_tasks(
    *,
    config: Any,
    renderer: Any,
    task_args: list[str],
) -> int:
    from adv_archon.core.executive_automation import (
        build_executive_automation_bundle,
        install_executive_automation,
        list_executive_automation_presets,
    )
    from adv_archon.core.tasks import TaskStore

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
    if command == "presets":
        presets = list_executive_automation_presets()
        lines = ["Presets de automatización ejecutiva:"]
        for preset in presets:
            lines.append(f"- {preset['name']} | {preset['description']}")
            for workflow in preset["launch_workflows"]:
                if workflow["times"]:
                    lines.append(
                        f"  {workflow['title']} | {', '.join(workflow['times'])}"
                    )
                elif workflow["interval_minutes"]:
                    lines.append(
                        f"  {workflow['title']} | cada {workflow['interval_minutes']} min"
                    )
            for task in preset["task_templates"]:
                lines.append(
                    f"  tarea: {task['title']} | {task['time']} | {task['category']}"
                )
        renderer.show_info("\n".join(lines))
        return 0
    if command == "install-executive":
        adv_command = shutil.which("adv-archon") or shutil.which("adv")
        if adv_command is None:
            renderer.show_error("No encuentro `adv-archon` en PATH.")
            return 1
        study_focus = " ".join(task_args[1:]).strip() or "tu linea actual de estudio"
        bundle = build_executive_automation_bundle(study_focus=study_focus)
        installed = install_executive_automation(
            store=store,
            adv_command=adv_command,
            bundle=bundle,
            timezone_name=config.tasks.default_timezone,
        )
        lines = [
            "Automatización ejecutiva instalada.",
            f"- launch agents: {len(installed.launch_agents)}",
            f"- tareas persistentes: {len(installed.tasks)}",
            f"- foco de estudio: {study_focus}",
        ]
        lines.extend(f"  {record.label}" for record in installed.launch_agents)
        lines.extend(f"  {task.title} | {task.due_at}" for task in installed.tasks)
        renderer.show_info("\n".join(lines))
        return 0
    renderer.show_error(
        "Uso: adv-archon tasks "
        "[list [open|all|done|due|cancelled]|run-due|presets|"
        "install-executive [foco]]"
    )
    return 1


def _handle_knowledge(
    *,
    config: Any,
    renderer: Any,
    knowledge_args: list[str],
    incognito: bool,
) -> int:
    from adv_archon.core.evals import evaluate_knowledge_retrieval
    from adv_archon.core.knowledge import KnowledgeStore, install_knowledge_launch_agent
    from adv_archon.core.memory import SentenceTransformerEncoder

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
        search_result = store.search_details(query, limit=config.knowledge.search_limit)
        records = search_result.records
        if not records:
            renderer.show_info("No encuentro conocimiento local relevante.")
            return 0
        retrieval_eval = evaluate_knowledge_retrieval(search_result)
        lines = [
            "Resultados de conocimiento local:",
            (
                "Estrategia: "
                f"{', '.join(search_result.plan.query_variants)} "
                f"| candidatos: {search_result.candidate_count}"
            ),
        ]
        if retrieval_eval is not None:
            confidence_map = {"high": "alta", "medium": "media", "low": "baja"}
            confidence_label = confidence_map.get(
                retrieval_eval.confidence,
                retrieval_eval.confidence,
            )
            lines.append(
                "Evaluacion: "
                f"confianza {confidence_label} "
                f"| cobertura maxima {retrieval_eval.max_term_coverage:.0%}"
            )
        for record in records:
            suffix = f" | {record.status}" if record.status != "indexed" else ""
            lines.append(f"- {record.title} | {record.path}{suffix}")
            coverage = f"{record.term_coverage:.0%}" if record.term_coverage else "0%"
            matched_terms = ", ".join(record.matched_terms) or "sin coincidencias directas"
            lines.append(
                f"  score={record.score} | cobertura={coverage} | matched={matched_terms}"
            )
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
    config: Any,
    renderer: Any,
    research_args: list[str],
    incognito: bool,
) -> int:
    from adv_archon.core.memory import SentenceTransformerEncoder
    from adv_archon.core.research import install_research_launch_agent, run_research_cycle
    from adv_archon.core.web_library import WebLibraryStore

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


def _handle_benchmark(
    *,
    config: Any,
    renderer: Any,
    project_root: Path,
    incognito: bool,
    benchmark_args: list[str],
) -> int:
    from adv_archon.core.benchmark import run_benchmarks
    from adv_archon.core.eval_store import EvalStore

    store = EvalStore(config.paths.evals_db)
    command = benchmark_args[0] if benchmark_args else "status"

    if command == "init":
        target = config.paths.benchmark_cases_file
        if target.exists():
            renderer.show_info(f"Ya existe un fichero de casos en {target}")
            return 0
        target.write_text(
            _bundled_benchmark_cases_path().read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        renderer.show_info(f"Casos de benchmark inicializados en {target}")
        return 0

    if command == "status":
        recent = store.list_recent_runs(limit=5)
        aggregate = store.summarize_metrics(suite=config.benchmark.default_suite)
        renderer.show_info(_render_benchmark_status(recent, aggregate))
        return 0

    if command == "run":
        cases_path = _resolve_benchmark_cases_path(config=config, benchmark_args=benchmark_args[1:])
        cases = _load_benchmark_cases(
            cases_path,
            cwd=project_root,
            home=Path.home(),
            max_cases=config.benchmark.max_cases,
        )
        if not cases:
            renderer.show_error("No hay casos de benchmark para ejecutar.")
            return 1

        run = store.register_run(
            suite=config.benchmark.default_suite,
            benchmark=config.benchmark.default_benchmark,
            model=_benchmark_model_label(config),
            status="running",
            started_at=datetime.now(UTC).isoformat(),
            git_sha=_git_sha(project_root),
            metadata={
                "cases_path": str(cases_path),
                "case_count": len(cases),
                "cwd": str(project_root),
            },
        )
        try:
            summary = run_benchmarks(
                cases,
                executor=_build_benchmark_executor(
                    config=config,
                    system_prompt=load_system_prompt(config.system_prompt_path),
                    project_root=project_root,
                    incognito=incognito,
                ),
            )
            for result in summary.results:
                usage = result.usage
                store.register_case(
                    run_id=run.id,
                    case_key=result.case.case_id,
                    status="error" if result.error else ("passed" if result.passed else "failed"),
                    score=result.overall_score,
                    latency_ms=round(result.duration_seconds * 1000, 2),
                    prompt_tokens=usage.prompt_tokens if usage is not None else 0,
                    completion_tokens=usage.completion_tokens if usage is not None else 0,
                    total_tokens=usage.total_tokens if usage is not None else 0,
                    estimated_cost_usd=usage.estimated_cost_usd if usage is not None else 0.0,
                    error_message=result.error,
                    metadata={
                        "prompt": result.case.prompt,
                        "tags": list(result.case.tags),
                        "grounding": _metric_payload(result.grounding),
                        "local_knowledge": _metric_payload(result.local_knowledge),
                        "confidence_citations": _metric_payload(
                            result.confidence_citations
                        ),
                        "citations": list(result.citations),
                        "provider": result.provider,
                        "model": result.model,
                    },
                )
            store.update_run(
                run.id,
                status="completed",
                completed_at=datetime.now(UTC).isoformat(),
                notes=f"{summary.passed_cases}/{summary.total_cases} casos pasados",
                metadata={
                    "cases_path": str(cases_path),
                    "case_count": len(cases),
                    "pass_rate": summary.pass_rate,
                    "average_score": summary.average_score,
                    "cwd": str(project_root),
                },
            )
        except Exception as exc:
            store.update_run(
                run.id,
                status="error",
                completed_at=datetime.now(UTC).isoformat(),
                notes=str(exc),
            )
            raise

        renderer.show_info(
            _render_benchmark_summary(summary, run_id=run.id, cases_path=cases_path)
        )
        return 0

    renderer.show_error(
        "Uso: adv-archon benchmark [status|init|run [cases.json]]"
    )
    return 1


def _build_benchmark_executor(
    *,
    config: Any,
    system_prompt: str,
    project_root: Path,
    incognito: bool,
) -> Any:
    from adv_archon.core.benchmark import BenchmarkEvidence

    def executor(case: Any) -> BenchmarkEvidence:
        quiet_renderer = Renderer(
            Console(file=io.StringIO(), force_terminal=False, no_color=True),
            show_tool_input=False,
        )
        app = ReplApp(
            config=config,
            llm=LLMRouter(config.llm),
            project_root=project_root,
            system_prompt=system_prompt,
            renderer=quiet_renderer,
            incognito=incognito,
        )
        try:
            runtime = app._runtime
            for seed in case.seed_memories:
                tags_value = seed.get("tags", ())
                tags = (
                    [str(item) for item in tags_value]
                    if isinstance(tags_value, list)
                    else []
                )
                importance_value = seed.get("importance", 3)
                importance = (
                    int(importance_value)
                    if isinstance(importance_value, int | float | str)
                    else 3
                )
                runtime.memory_store.remember(
                    str(seed.get("content", "")),
                    tags,
                    source="benchmark",
                    memory_type=str(seed.get("memory_type", "fact")),
                    namespace=str(seed.get("namespace", "general")),
                    category=str(seed.get("category", "general")),
                    importance=importance,
                    metadata={"seeded_for_case": case.case_id},
                )
            inspection = app._agent.inspect_turn(case.prompt)
            result = app._agent.run_turn(case.prompt)
            return BenchmarkEvidence(
                response_text=result.reply,
                knowledge_eval=inspection.knowledge_eval,
                used_local_knowledge=bool(inspection.local_knowledge_hits),
                local_knowledge_hits=inspection.local_knowledge_hits,
                memory_hits=inspection.memory_hits,
                provider=result.usage.provider,
                model=result.usage.model,
                usage=result.usage.usage,
            )
        finally:
            app._shutdown()

    return executor


def _resolve_benchmark_cases_path(
    *,
    config: Any,
    benchmark_args: list[str],
) -> Path:
    if benchmark_args:
        return Path(benchmark_args[0]).expanduser()
    if config.paths.benchmark_cases_file.exists():
        return cast(Path, config.paths.benchmark_cases_file)
    return _bundled_benchmark_cases_path()


def _bundled_benchmark_cases_path() -> Path:
    return Path(__file__).resolve().parent / "resources" / "benchmark_cases.json"


def _load_benchmark_cases(
    cases_path: Path,
    *,
    cwd: Path,
    home: Path,
    max_cases: int,
) -> list[Any]:
    from adv_archon.core.benchmark import BenchmarkCase

    raw = json.loads(cases_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("El fichero de casos debe contener una lista JSON.")
    replacements = {"{cwd}": str(cwd), "{home}": str(home)}
    cases: list[Any] = []
    for item in raw[: max(1, max_cases)]:
        if not isinstance(item, dict):
            continue
        prompt = str(item.get("prompt", ""))
        for placeholder, value in replacements.items():
            prompt = prompt.replace(placeholder, value)
        raw_seed_memories = item.get("seed_memories", [])
        seed_memories = tuple(
            cast(dict[str, object], entry)
            for entry in raw_seed_memories
            if isinstance(entry, dict)
        )
        cases.append(
            BenchmarkCase(
                case_id=str(item.get("case_id", f"case-{len(cases) + 1}")),
                prompt=prompt,
                seed_memories=seed_memories,
                expected_facts=tuple(str(value) for value in item.get("expected_facts", [])),
                forbidden_facts=tuple(
                    str(value) for value in item.get("forbidden_facts", [])
                ),
                expected_citation_hints=tuple(
                    str(value) for value in item.get("expected_citation_hints", [])
                ),
                require_local_knowledge=bool(item.get("require_local_knowledge", False)),
                require_confidence_block=bool(item.get("require_confidence_block", False)),
                require_memory=bool(item.get("require_memory", False)),
                expected_memory_hints=tuple(
                    str(value) for value in item.get("expected_memory_hints", [])
                ),
                max_duration_seconds=(
                    float(item["max_duration_seconds"])
                    if item.get("max_duration_seconds") is not None
                    else None
                ),
                pass_threshold=float(item.get("pass_threshold", 0.7)),
                tags=tuple(str(value) for value in item.get("tags", [])),
            )
        )
    return cases


def _benchmark_model_label(config: Any) -> str:
    if config.llm.mode == "local":
        return f"ollama/{config.llm.ollama_model}"
    return f"gemini/{config.llm.gemini_model}"


def _git_sha(project_root: Path) -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _metric_payload(metric: Any) -> dict[str, Any]:
    return {
        "name": getattr(metric, "name", ""),
        "score": getattr(metric, "score", 0.0),
        "passed": bool(getattr(metric, "passed", False)),
        "details": list(getattr(metric, "details", ()) or ()),
    }


def _render_benchmark_status(recent: list[Any], aggregate: Any) -> str:
    pass_rate = aggregate.pass_rate if aggregate.pass_rate is not None else "n/a"
    avg_score = aggregate.avg_score if aggregate.avg_score is not None else "n/a"
    avg_latency = aggregate.avg_latency_ms if aggregate.avg_latency_ms is not None else "n/a"
    lines = [
        "Estado de benchmarks internos:",
        f"- runs: {aggregate.run_count} | casos: {aggregate.case_count} | pass rate: {pass_rate}",
        f"- score medio: {avg_score} | latencia media ms: {avg_latency}",
    ]
    if recent:
        lines.append("Runs recientes:")
        for item in recent:
            lines.append(
                f"- [#{item.run.id}] {item.run.suite}/{item.run.benchmark} "
                f"| {item.run.model} | {item.run.status} | pass rate {item.pass_rate}"
            )
    else:
        lines.append("- no hay runs guardados todavia")
    return "\n".join(lines)


def _render_benchmark_summary(
    summary: Any,
    *,
    run_id: int,
    cases_path: Path,
) -> str:
    lines = [
        f"Benchmark interno completado | run #{run_id}",
        f"- casos: {summary.total_cases}",
        f"- pasados: {summary.passed_cases}",
        f"- fallidos: {summary.failed_cases}",
        f"- pass rate: {summary.pass_rate:.0%}",
        f"- score medio: {summary.average_score:.2f}",
        f"- grounding medio: {summary.average_grounding:.2f}",
        f"- conocimiento local medio: {summary.average_local_knowledge:.2f}",
        f"- memoria media: {summary.average_memory_recall:.2f}",
        f"- citas/confianza medio: {summary.average_confidence_citations:.2f}",
        f"- latencia media: {summary.average_latency_score:.2f}",
        f"- duracion total s: {summary.total_duration_seconds:.2f}",
        f"- casos usados: {cases_path}",
    ]
    failures = [result for result in summary.results if not result.passed][:3]
    if failures:
        lines.append("Casos a revisar:")
        for result in failures:
            lines.append(
                f"- {result.case.case_id} | score {result.overall_score:.2f} "
                f"| error: {result.error or 'sin error'}"
            )
    return "\n".join(lines)


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
    renderer = Renderer(Console(), show_tool_input=config.ui.show_tool_input)
    project_root = Path.cwd()

    if args.prompt == "daily":
        return _handle_daily(
            config=config,
            renderer=renderer,
            project_root=project_root,
            incognito=args.incognito,
            daily_args=args.paths,
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

    if args.prompt == "benchmark":
        return _handle_benchmark(
            config=config,
            renderer=renderer,
            project_root=project_root,
            incognito=args.incognito,
            benchmark_args=args.paths,
        )

    if args.prompt == "desktop-bundle":
        return _handle_desktop_bundle(
            renderer=renderer,
            bundle_args=args.paths,
        )

    system_prompt = load_system_prompt(config.system_prompt_path)

    if args.prompt == "desktop":
        return launch_desktop_app(
            config=config,
            llm=llm,
            project_root=project_root,
            system_prompt=system_prompt,
            incognito=args.incognito,
        )

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
        prompt = format_prompt_with_attachments(args.prompt, args.paths, label="Referenced paths")
        return cast(int, app.ask_once(prompt))

    return cast(int, app.run())


if __name__ == "__main__":
    raise SystemExit(main())
