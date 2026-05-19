from __future__ import annotations

import sqlite3
from pathlib import Path

from adv_archon.core.config import (
    DEFAULT_SYSTEM_PROMPT,
    AppConfig,
    BenchmarkConfig,
    BrowserConfig,
    FileAccessConfig,
    GoogleConfig,
    KnowledgeConfig,
    LLMConfig,
    MemoryConfig,
    PathsConfig,
    ProfilesConfig,
    ResearchConfig,
    ShellConfig,
    TasksConfig,
    TeamConfig,
    UIConfig,
    VoiceConfig,
    WebConfig,
)
from adv_archon.core.performance_profiler import (
    PerformanceFinding,
    PerformanceProbe,
    PerformanceProfiler,
    PerformanceReport,
)


def _config(tmp_path: Path, *, keep_alive: str = "-1") -> AppConfig:
    paths = PathsConfig(root=tmp_path)
    return AppConfig(
        paths=paths,
        llm=LLMConfig(
            ollama_model="llama3.1:8b",
            fast_local_model="llama3.2:3b",
            planner_local_model="llama3.2:3b",
            ollama_keep_alive=keep_alive,
        ),
        ui=UIConfig(),
        memory=MemoryConfig(),
        knowledge=KnowledgeConfig(default_roots=()),
        files=FileAccessConfig(allowed_roots=(str(tmp_path),)),
        shell=ShellConfig(),
        tasks=TasksConfig(),
        browser=BrowserConfig(),
        web=WebConfig(),
        voice=VoiceConfig(),
        google=GoogleConfig(),
        research=ResearchConfig(),
        benchmark=BenchmarkConfig(),
        profiles=ProfilesConfig(),
        team=TeamConfig(),
        system_prompt_path=DEFAULT_SYSTEM_PROMPT,
    )


def _project_root(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    desktop = root / "src" / "adv_archon" / "desktop"
    desktop.mkdir(parents=True)
    (desktop / "warmup_agent.py").write_text("# warmup\n", encoding="utf-8")
    (desktop / "workers.py").write_text("# workers\n", encoding="utf-8")
    return root


def _official_overrides() -> dict[str, object]:
    return {
        "geocodificacion_nominatim": lambda: {
            "municipality": "Madrid",
            "province": "Madrid",
        },
        "catastro_ovc": lambda: {
            "cadastral_ref": "2807901VK4720G0001ZX",
            "ok": True,
        },
        "snczi_cnig": lambda: {"in_flood_zone": False, "ok": True},
        "red_natura_2000_cnig": lambda: {"in_protected_area": False, "ok": True},
        "costas_sigcostas": lambda: {"in_public_domain": False, "ok": True},
        "carreteras_idee": lambda: {"in_affection_zone": False, "ok": True},
        "pgou_sqlite": lambda: {"indexed_count": 3, "madrid_indexed": True},
    }


def _probe_by_name(report: PerformanceReport, name: str) -> PerformanceProbe:
    return next(probe for probe in report.probes if probe.name == name)


def test_profiler_runs_offline_with_archon_specific_probes(tmp_path: Path) -> None:
    profiler = PerformanceProfiler(
        _config(tmp_path),
        project_root=_project_root(tmp_path),
        official_probe_overrides=_official_overrides(),  # type: ignore[arg-type]
    )

    report = profiler.run(include_ollama=False, include_qthread=False)

    names = {probe.name for probe in report.probes}
    assert "warmup_agent" in names
    assert "desktop_workers" in names
    assert "geocodificacion_nominatim" in names
    assert "catastro_ovc" in names
    assert "snczi_cnig" in names
    assert "red_natura_2000_cnig" in names
    assert "costas_sigcostas" in names
    assert "carreteras_idee" in names
    assert "pgou_sqlite" in names
    assert "generate_expediente_pdf" in names
    assert _probe_by_name(report, "catastro_ovc").metadata["cadastral_ref"]


def test_sqlite_probe_reports_metadata_without_json_cache(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.paths.root.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(config.paths.pgou_db) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE municipios (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO municipios (name) VALUES ('Madrid')")

    profiler = PerformanceProfiler(config, project_root=_project_root(tmp_path))
    report = profiler.run(
        include_ollama=False,
        include_qthread=False,
        include_official_sources=False,
    )

    pgou_probe = _probe_by_name(report, "pgou_db")
    assert pgou_probe.status == "ok"
    assert pgou_probe.metadata["table_count"] >= 1
    assert pgou_probe.metadata["journal_mode"] in {"wal", "memory"}
    assert not list(tmp_path.glob("*.json"))


def test_slow_ollama_finding_is_actionable_for_adv_archon(tmp_path: Path) -> None:
    profiler = PerformanceProfiler(_config(tmp_path), project_root=_project_root(tmp_path))
    probes = [
        PerformanceProbe(
            name="ollama_ttft",
            category="ollama",
            elapsed_ms=12_500,
            status="ok",
            detail="Streaming local medido con /api/chat",
            metadata={"ttft_ms": 12_500, "tokens_per_second": 7.0},
        )
    ]

    findings = profiler._build_findings(probes)  # noqa: SLF001
    text = "\n".join(f"{item.title} {item.recommendation}" for item in findings)

    assert "Primer token demasiado lento" in text
    assert "warmup_agent.py" in text
    assert "llama3.2:3b" in text
    assert "modelos grandes" in text


def test_missing_ollama_model_recommends_pull_or_settings(tmp_path: Path) -> None:
    profiler = PerformanceProfiler(_config(tmp_path), project_root=_project_root(tmp_path))
    probes = [
        PerformanceProbe(
            name="ollama_model_available",
            category="ollama",
            elapsed_ms=0,
            status="warning",
            detail="Modelo local activo `llama3.1:8b` no visible",
            metadata={"available_models": ["llama3.2:3b"]},
        )
    ]

    findings = profiler._build_findings(probes)  # noqa: SLF001

    assert any("ollama pull llama3.1:8b" in item.recommendation for item in findings)
    assert any("Ajustes" in item.recommendation for item in findings)


def test_pdf_generation_probe_is_direct_and_non_llm(tmp_path: Path) -> None:
    profiler = PerformanceProfiler(_config(tmp_path), project_root=_project_root(tmp_path))

    report = profiler.run(
        include_ollama=False,
        include_qthread=False,
        include_official_sources=False,
    )

    pdf_probe = _probe_by_name(report, "generate_expediente_pdf")
    assert pdf_probe.status == "ok"
    assert pdf_probe.detail == "Generación PDF directa sin LLM"
    assert pdf_probe.metadata["pdf_bytes"] > 1000


def test_report_markdown_is_actionable_not_generic() -> None:
    report = PerformanceReport(
        generated_at="2026-05-19T12:00:00+00:00",
        project="ADV ARCHON Studio Workspace",
        active_model="llama3.1:8b",
        fast_model="llama3.2:3b",
        probes=(
            PerformanceProbe(
                "warmup_agent",
                "architecture",
                0,
                "ok",
                "warmup_agent.py localizado",
            ),
        ),
        findings=(
            PerformanceFinding(
                "warning",
                "Ollama",
                "El modelo local entra frío.",
                "Precalentar al arrancar con warmup_agent.py.",
                "TTFT 4500 ms.",
            ),
        ),
    )

    markdown = report.render_markdown()

    assert "ADV ARCHON Performance Profiler" in markdown
    assert "Diagnóstico accionable" in markdown
    assert "Modelo principal: `llama3.1:8b`" in markdown
    assert "warmup_agent.py" in markdown
