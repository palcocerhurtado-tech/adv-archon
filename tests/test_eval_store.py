from pathlib import Path

import pytest

from adv_archon.core.eval_store import EvalStore


def test_eval_store_persists_runs_and_recent_summaries(tmp_path: Path) -> None:
    db_path = tmp_path / "evals.db"
    store = EvalStore(db_path)

    run = store.register_run(
        suite="nightly",
        benchmark="response-quality",
        model="gemini-2.5-flash",
        status="completed",
        started_at="2026-04-24T08:00:00+00:00",
        completed_at="2026-04-24T08:02:00+00:00",
        git_sha="abc123",
        notes="Regression batch",
        metadata={"profile": "coding", "trigger": "ci"},
    )
    store.register_case(
        run_id=run.id,
        case_key="answer-001",
        status="passed",
        score=0.9,
        latency_ms=120.5,
        prompt_tokens=100,
        completion_tokens=40,
        estimated_cost_usd=0.001,
        metadata={"topic": "search"},
    )
    store.register_case(
        run_id=run.id,
        case_key="answer-002",
        status="failed",
        score=0.25,
        latency_ms=240.0,
        prompt_tokens=80,
        completion_tokens=20,
        estimated_cost_usd=0.0008,
        error_message="score below threshold",
    )

    reloaded = EvalStore(db_path)
    recent = reloaded.list_recent_runs()

    assert len(recent) == 1
    assert recent[0].run.suite == "nightly"
    assert recent[0].run.benchmark == "response-quality"
    assert recent[0].run.model == "gemini-2.5-flash"
    assert recent[0].run.git_sha == "abc123"
    assert recent[0].run.metadata == {"profile": "coding", "trigger": "ci"}
    assert recent[0].case_count == 2
    assert recent[0].passed_cases == 1
    assert recent[0].failed_cases == 1
    assert recent[0].error_cases == 0
    assert recent[0].pass_rate == pytest.approx(0.5)
    assert recent[0].avg_score == pytest.approx(0.575)
    assert recent[0].avg_latency_ms == pytest.approx(180.25)
    assert recent[0].total_prompt_tokens == 180
    assert recent[0].total_completion_tokens == 60
    assert recent[0].total_tokens == 240
    assert recent[0].estimated_cost_usd == pytest.approx(0.0018)


def test_eval_store_register_case_upserts_by_run_and_case_key(tmp_path: Path) -> None:
    store = EvalStore(tmp_path / "evals.db")
    run = store.register_run(
        suite="smoke",
        benchmark="tool-use",
        model="ollama/llama3.1:8b",
        status="running",
    )

    first = store.register_case(
        run_id=run.id,
        case_key="tool-001",
        status="failed",
        score=0.2,
        latency_ms=320.0,
        prompt_tokens=30,
        completion_tokens=12,
        estimated_cost_usd=0.0004,
        error_message="timeout",
    )
    updated = store.register_case(
        run_id=run.id,
        case_key="tool-001",
        status="passed",
        score=0.95,
        latency_ms=110.0,
        prompt_tokens=18,
        completion_tokens=6,
        estimated_cost_usd=0.0002,
        error_message=None,
        metadata={"retry": 1},
    )
    summary = store.summarize_metrics(run_id=run.id)

    assert updated.id == first.id
    assert updated.status == "passed"
    assert updated.error_message is None
    assert updated.metadata == {"retry": 1}
    assert summary.run_count == 1
    assert summary.case_count == 1
    assert summary.passed_cases == 1
    assert summary.failed_cases == 0
    assert summary.error_cases == 0
    assert summary.pass_rate == pytest.approx(1.0)
    assert summary.avg_score == pytest.approx(0.95)
    assert summary.avg_latency_ms == pytest.approx(110.0)
    assert summary.total_prompt_tokens == 18
    assert summary.total_completion_tokens == 6
    assert summary.total_tokens == 24
    assert summary.estimated_cost_usd == pytest.approx(0.0002)


def test_eval_store_summarize_metrics_supports_filters_and_empty_results(
    tmp_path: Path,
) -> None:
    store = EvalStore(tmp_path / "evals.db")

    smoke_run = store.register_run(
        suite="smoke",
        benchmark="retrieval",
        model="gemini-2.5-flash",
        status="completed",
    )
    nightly_run = store.register_run(
        suite="nightly",
        benchmark="retrieval",
        model="gemini-2.5-flash",
        status="completed",
    )
    store.register_case(
        run_id=smoke_run.id,
        case_key="search-001",
        status="passed",
        score=1.0,
        latency_ms=95.0,
        prompt_tokens=10,
        completion_tokens=4,
        estimated_cost_usd=0.0001,
    )
    store.register_case(
        run_id=nightly_run.id,
        case_key="search-002",
        status="error",
        latency_ms=410.0,
        prompt_tokens=20,
        completion_tokens=10,
        estimated_cost_usd=0.0005,
        error_message="tool timeout",
    )

    smoke_summary = store.summarize_metrics(suite="smoke")
    missing_summary = store.summarize_metrics(suite="adhoc")
    recent_smoke_runs = store.list_recent_runs(suite="smoke")

    assert smoke_summary.run_count == 1
    assert smoke_summary.case_count == 1
    assert smoke_summary.passed_cases == 1
    assert smoke_summary.failed_cases == 0
    assert smoke_summary.error_cases == 0
    assert smoke_summary.pass_rate == pytest.approx(1.0)
    assert smoke_summary.avg_score == pytest.approx(1.0)
    assert smoke_summary.total_tokens == 14
    assert smoke_summary.estimated_cost_usd == pytest.approx(0.0001)
    assert len(recent_smoke_runs) == 1
    assert recent_smoke_runs[0].run.id == smoke_run.id

    assert missing_summary.run_count == 0
    assert missing_summary.case_count == 0
    assert missing_summary.passed_cases == 0
    assert missing_summary.failed_cases == 0
    assert missing_summary.error_cases == 0
    assert missing_summary.pass_rate is None
    assert missing_summary.avg_score is None
    assert missing_summary.avg_latency_ms is None
    assert missing_summary.total_tokens == 0
    assert missing_summary.estimated_cost_usd == pytest.approx(0.0)


def test_eval_store_requires_existing_run_for_cases(tmp_path: Path) -> None:
    store = EvalStore(tmp_path / "evals.db")

    with pytest.raises(ValueError, match="No existe ningun run de evaluacion"):
        store.register_case(
            run_id=999,
            case_key="missing-run",
            status="error",
        )


def test_eval_store_uses_sqlite_wal_mode_for_persistent_db(tmp_path: Path) -> None:
    store = EvalStore(tmp_path / "evals.db")

    journal_mode = store._conn.execute("PRAGMA journal_mode").fetchone()[0]
    busy_timeout = store._conn.execute("PRAGMA busy_timeout").fetchone()[0]
    foreign_keys = store._conn.execute("PRAGMA foreign_keys").fetchone()[0]

    assert str(journal_mode).lower() == "wal"
    assert int(busy_timeout) == 30000
    assert int(foreign_keys) == 1


def test_eval_store_update_run_persists_completion_and_metadata(tmp_path: Path) -> None:
    store = EvalStore(tmp_path / "evals.db")
    run = store.register_run(
        suite="smoke",
        benchmark="real-cases",
        model="ollama/llama3.1:8b",
        status="running",
    )

    updated = store.update_run(
        run.id,
        status="completed",
        completed_at="2026-04-24T10:15:00+00:00",
        notes="3/3 casos pasados",
        metadata={"pass_rate": 1.0},
    )

    assert updated.status == "completed"
    assert updated.completed_at == "2026-04-24T10:15:00+00:00"
    assert updated.notes == "3/3 casos pasados"
    assert updated.metadata == {"pass_rate": 1.0}
