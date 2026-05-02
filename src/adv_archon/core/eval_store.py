from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class EvalRunRecord:
    id: int
    suite: str
    benchmark: str
    model: str
    status: str
    git_sha: str | None
    notes: str | None
    metadata: dict[str, Any]
    started_at: str
    completed_at: str | None
    created_at: str
    updated_at: str


@dataclass(slots=True)
class EvalCaseRecord:
    id: int
    run_id: int
    case_key: str
    status: str
    score: float | None
    latency_ms: float | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    error_message: str | None
    metadata: dict[str, Any]
    created_at: str
    updated_at: str


@dataclass(slots=True)
class EvalRunSummary:
    run: EvalRunRecord
    case_count: int
    passed_cases: int
    failed_cases: int
    error_cases: int
    pass_rate: float | None
    avg_score: float | None
    avg_latency_ms: float | None
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float


@dataclass(slots=True)
class EvalAggregateSummary:
    run_count: int
    case_count: int
    passed_cases: int
    failed_cases: int
    error_cases: int
    pass_rate: float | None
    avg_score: float | None
    avg_latency_ms: float | None
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float


class EvalStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn = self._connect()

    def register_run(
        self,
        *,
        suite: str,
        benchmark: str,
        model: str,
        status: str = "running",
        started_at: str | None = None,
        completed_at: str | None = None,
        git_sha: str | None = None,
        notes: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvalRunRecord:
        now = _utc_now()
        cursor = self._conn.execute(
            """
            INSERT INTO eval_runs (
                suite,
                benchmark,
                model,
                status,
                git_sha,
                notes,
                metadata_json,
                started_at,
                completed_at,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _require_text(suite, "La suite de evaluacion es obligatoria."),
                _require_text(benchmark, "El benchmark de evaluacion es obligatorio."),
                _require_text(model, "El modelo de evaluacion es obligatorio."),
                _require_text(status, "El estado del run es obligatorio."),
                _clean_optional_text(git_sha),
                _clean_optional_text(notes),
                _dump_json_dict(metadata),
                started_at or now,
                _clean_optional_text(completed_at),
                now,
                now,
            ),
        )
        self._conn.commit()
        if cursor.lastrowid is None:
            raise RuntimeError("SQLite no devolvio el id del run de evaluacion.")
        record = self._get_run(int(cursor.lastrowid))
        if record is None:
            raise RuntimeError("No he podido recuperar el run de evaluacion guardado.")
        return record

    def register_case(
        self,
        *,
        run_id: int,
        case_key: str,
        status: str,
        score: float | None = None,
        latency_ms: float | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int | None = None,
        estimated_cost_usd: float = 0.0,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvalCaseRecord:
        clean_run_id = _require_positive_int(run_id, "El run_id debe ser mayor que cero.")
        self._ensure_run_exists(clean_run_id)

        clean_prompt_tokens = _require_non_negative_int(
            prompt_tokens,
            "prompt_tokens no puede ser negativo.",
        )
        clean_completion_tokens = _require_non_negative_int(
            completion_tokens,
            "completion_tokens no puede ser negativo.",
        )
        clean_total_tokens = (
            clean_prompt_tokens + clean_completion_tokens
            if total_tokens is None
            else _require_non_negative_int(total_tokens, "total_tokens no puede ser negativo.")
        )
        clean_latency_ms = (
            None
            if latency_ms is None
            else _require_non_negative_float(latency_ms, "latency_ms no puede ser negativa.")
        )
        clean_cost = _require_non_negative_float(
            estimated_cost_usd,
            "estimated_cost_usd no puede ser negativo.",
        )
        now = _utc_now()
        clean_case_key = _require_text(case_key, "La clave del caso es obligatoria.")

        self._conn.execute(
            """
            INSERT INTO eval_cases (
                run_id,
                case_key,
                status,
                score,
                latency_ms,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                estimated_cost_usd,
                error_message,
                metadata_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, case_key) DO UPDATE SET
                status = excluded.status,
                score = excluded.score,
                latency_ms = excluded.latency_ms,
                prompt_tokens = excluded.prompt_tokens,
                completion_tokens = excluded.completion_tokens,
                total_tokens = excluded.total_tokens,
                estimated_cost_usd = excluded.estimated_cost_usd,
                error_message = excluded.error_message,
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at
            """,
            (
                clean_run_id,
                clean_case_key,
                _require_text(status, "El estado del caso es obligatorio."),
                score,
                clean_latency_ms,
                clean_prompt_tokens,
                clean_completion_tokens,
                clean_total_tokens,
                clean_cost,
                _clean_optional_text(error_message),
                _dump_json_dict(metadata),
                now,
                now,
            ),
        )
        self._conn.execute(
            "UPDATE eval_runs SET updated_at = ? WHERE id = ?",
            (now, clean_run_id),
        )
        self._conn.commit()

        record = self._get_case(clean_run_id, clean_case_key)
        if record is None:
            raise RuntimeError("No he podido recuperar el caso de evaluacion guardado.")
        return record

    def update_run(
        self,
        run_id: int,
        *,
        status: str | None = None,
        completed_at: str | None = None,
        notes: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvalRunRecord:
        clean_run_id = _require_positive_int(run_id, "El run_id debe ser mayor que cero.")
        self._ensure_run_exists(clean_run_id)
        current = self._get_run(clean_run_id)
        if current is None:
            raise RuntimeError("No he podido recuperar el run de evaluacion a actualizar.")

        now = _utc_now()
        next_status = (
            _require_text(status, "El estado del run es obligatorio.")
            if status
            else current.status
        )
        next_notes = current.notes if notes is None else _clean_optional_text(notes)
        next_completed_at = completed_at if completed_at is not None else current.completed_at
        next_metadata = metadata if metadata is not None else current.metadata

        self._conn.execute(
            """
            UPDATE eval_runs
            SET status = ?,
                completed_at = ?,
                notes = ?,
                metadata_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                next_status,
                _clean_optional_text(next_completed_at),
                next_notes,
                _dump_json_dict(next_metadata),
                now,
                clean_run_id,
            ),
        )
        self._conn.commit()
        record = self._get_run(clean_run_id)
        if record is None:
            raise RuntimeError("No he podido recuperar el run de evaluacion actualizado.")
        return record

    def list_recent_runs(
        self,
        *,
        limit: int = 10,
        suite: str | None = None,
        benchmark: str | None = None,
        model: str | None = None,
        status: str | None = None,
    ) -> list[EvalRunSummary]:
        if limit <= 0:
            return []

        where_clause, params = _build_run_filters(
            suite=suite,
            benchmark=benchmark,
            model=model,
            status=status,
        )
        rows = self._conn.execute(
            f"""
            SELECT
                r.id,
                r.suite,
                r.benchmark,
                r.model,
                r.status,
                r.git_sha,
                r.notes,
                r.metadata_json,
                r.started_at,
                r.completed_at,
                r.created_at,
                r.updated_at,
                COUNT(c.id) AS case_count,
                COALESCE(SUM(CASE WHEN c.status = 'passed' THEN 1 ELSE 0 END), 0)
                    AS passed_cases,
                COALESCE(SUM(CASE WHEN c.status = 'failed' THEN 1 ELSE 0 END), 0)
                    AS failed_cases,
                COALESCE(SUM(CASE WHEN c.status = 'error' THEN 1 ELSE 0 END), 0)
                    AS error_cases,
                AVG(c.score) AS avg_score,
                AVG(c.latency_ms) AS avg_latency_ms,
                COALESCE(SUM(c.prompt_tokens), 0) AS total_prompt_tokens,
                COALESCE(SUM(c.completion_tokens), 0) AS total_completion_tokens,
                COALESCE(SUM(c.total_tokens), 0) AS total_tokens,
                COALESCE(SUM(c.estimated_cost_usd), 0.0) AS estimated_cost_usd
            FROM eval_runs r
            LEFT JOIN eval_cases c ON c.run_id = r.id
            {where_clause}
            GROUP BY
                r.id,
                r.suite,
                r.benchmark,
                r.model,
                r.status,
                r.git_sha,
                r.notes,
                r.metadata_json,
                r.started_at,
                r.completed_at,
                r.created_at,
                r.updated_at
            ORDER BY r.updated_at DESC, r.id DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
        return [self._row_to_run_summary(row) for row in rows]

    def summarize_metrics(
        self,
        *,
        run_id: int | None = None,
        suite: str | None = None,
        benchmark: str | None = None,
        model: str | None = None,
        status: str | None = None,
    ) -> EvalAggregateSummary:
        where_clause, params = _build_run_filters(
            run_id=run_id,
            suite=suite,
            benchmark=benchmark,
            model=model,
            status=status,
        )
        row = self._conn.execute(
            f"""
            SELECT
                COUNT(DISTINCT r.id) AS run_count,
                COUNT(c.id) AS case_count,
                COALESCE(SUM(CASE WHEN c.status = 'passed' THEN 1 ELSE 0 END), 0)
                    AS passed_cases,
                COALESCE(SUM(CASE WHEN c.status = 'failed' THEN 1 ELSE 0 END), 0)
                    AS failed_cases,
                COALESCE(SUM(CASE WHEN c.status = 'error' THEN 1 ELSE 0 END), 0)
                    AS error_cases,
                AVG(c.score) AS avg_score,
                AVG(c.latency_ms) AS avg_latency_ms,
                COALESCE(SUM(c.prompt_tokens), 0) AS total_prompt_tokens,
                COALESCE(SUM(c.completion_tokens), 0) AS total_completion_tokens,
                COALESCE(SUM(c.total_tokens), 0) AS total_tokens,
                COALESCE(SUM(c.estimated_cost_usd), 0.0) AS estimated_cost_usd
            FROM eval_runs r
            LEFT JOIN eval_cases c ON c.run_id = r.id
            {where_clause}
            """,
            params,
        ).fetchone()
        if row is None:
            return EvalAggregateSummary(
                run_count=0,
                case_count=0,
                passed_cases=0,
                failed_cases=0,
                error_cases=0,
                pass_rate=None,
                avg_score=None,
                avg_latency_ms=None,
                total_prompt_tokens=0,
                total_completion_tokens=0,
                total_tokens=0,
                estimated_cost_usd=0.0,
            )
        return self._row_to_aggregate_summary(row)

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            self._db_path,
            timeout=30.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA foreign_keys = ON")
        self._ensure_schema(conn)
        return conn

    @staticmethod
    def _ensure_schema(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS eval_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                suite TEXT NOT NULL,
                benchmark TEXT NOT NULL,
                model TEXT NOT NULL,
                status TEXT NOT NULL,
                git_sha TEXT,
                notes TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                started_at TEXT NOT NULL,
                completed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS eval_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                case_key TEXT NOT NULL,
                status TEXT NOT NULL,
                score REAL,
                latency_ms REAL,
                prompt_tokens INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                estimated_cost_usd REAL NOT NULL DEFAULT 0.0,
                error_message TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES eval_runs(id) ON DELETE CASCADE,
                UNIQUE (run_id, case_key)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_eval_runs_updated_at
            ON eval_runs (updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_eval_runs_suite_benchmark
            ON eval_runs (suite, benchmark, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_eval_cases_run_id
            ON eval_cases (run_id, created_at ASC)
            """
        )
        conn.commit()

    def _ensure_run_exists(self, run_id: int) -> None:
        row = self._conn.execute(
            "SELECT id FROM eval_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"No existe ningun run de evaluacion con id {run_id}.")

    def _get_run(self, run_id: int) -> EvalRunRecord | None:
        row = self._conn.execute(
            """
            SELECT
                id,
                suite,
                benchmark,
                model,
                status,
                git_sha,
                notes,
                metadata_json,
                started_at,
                completed_at,
                created_at,
                updated_at
            FROM eval_runs
            WHERE id = ?
            """,
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return _row_to_run_record(row)

    def _get_case(self, run_id: int, case_key: str) -> EvalCaseRecord | None:
        row = self._conn.execute(
            """
            SELECT
                id,
                run_id,
                case_key,
                status,
                score,
                latency_ms,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                estimated_cost_usd,
                error_message,
                metadata_json,
                created_at,
                updated_at
            FROM eval_cases
            WHERE run_id = ? AND case_key = ?
            """,
            (run_id, case_key),
        ).fetchone()
        if row is None:
            return None
        return _row_to_case_record(row)

    @staticmethod
    def _row_to_run_summary(row: sqlite3.Row) -> EvalRunSummary:
        case_count = int(row["case_count"])
        passed_cases = int(row["passed_cases"])
        return EvalRunSummary(
            run=_row_to_run_record(row),
            case_count=case_count,
            passed_cases=passed_cases,
            failed_cases=int(row["failed_cases"]),
            error_cases=int(row["error_cases"]),
            pass_rate=_compute_pass_rate(passed_cases, case_count),
            avg_score=_round_optional(row["avg_score"]),
            avg_latency_ms=_round_optional(row["avg_latency_ms"]),
            total_prompt_tokens=int(row["total_prompt_tokens"]),
            total_completion_tokens=int(row["total_completion_tokens"]),
            total_tokens=int(row["total_tokens"]),
            estimated_cost_usd=round(float(row["estimated_cost_usd"]), 6),
        )

    @staticmethod
    def _row_to_aggregate_summary(row: sqlite3.Row) -> EvalAggregateSummary:
        case_count = int(row["case_count"])
        passed_cases = int(row["passed_cases"])
        return EvalAggregateSummary(
            run_count=int(row["run_count"]),
            case_count=case_count,
            passed_cases=passed_cases,
            failed_cases=int(row["failed_cases"]),
            error_cases=int(row["error_cases"]),
            pass_rate=_compute_pass_rate(passed_cases, case_count),
            avg_score=_round_optional(row["avg_score"]),
            avg_latency_ms=_round_optional(row["avg_latency_ms"]),
            total_prompt_tokens=int(row["total_prompt_tokens"]),
            total_completion_tokens=int(row["total_completion_tokens"]),
            total_tokens=int(row["total_tokens"]),
            estimated_cost_usd=round(float(row["estimated_cost_usd"]), 6),
        )


def _row_to_run_record(row: sqlite3.Row) -> EvalRunRecord:
    return EvalRunRecord(
        id=int(row["id"]),
        suite=str(row["suite"]),
        benchmark=str(row["benchmark"]),
        model=str(row["model"]),
        status=str(row["status"]),
        git_sha=str(row["git_sha"]) if row["git_sha"] is not None else None,
        notes=str(row["notes"]) if row["notes"] is not None else None,
        metadata=_load_json_dict(row["metadata_json"]),
        started_at=str(row["started_at"]),
        completed_at=str(row["completed_at"]) if row["completed_at"] is not None else None,
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _row_to_case_record(row: sqlite3.Row) -> EvalCaseRecord:
    return EvalCaseRecord(
        id=int(row["id"]),
        run_id=int(row["run_id"]),
        case_key=str(row["case_key"]),
        status=str(row["status"]),
        score=float(row["score"]) if row["score"] is not None else None,
        latency_ms=float(row["latency_ms"]) if row["latency_ms"] is not None else None,
        prompt_tokens=int(row["prompt_tokens"]),
        completion_tokens=int(row["completion_tokens"]),
        total_tokens=int(row["total_tokens"]),
        estimated_cost_usd=float(row["estimated_cost_usd"]),
        error_message=(
            str(row["error_message"]) if row["error_message"] is not None else None
        ),
        metadata=_load_json_dict(row["metadata_json"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _build_run_filters(
    *,
    run_id: int | None = None,
    suite: str | None = None,
    benchmark: str | None = None,
    model: str | None = None,
    status: str | None = None,
) -> tuple[str, list[object]]:
    clauses: list[str] = []
    params: list[object] = []

    if run_id is not None:
        clauses.append("r.id = ?")
        params.append(_require_positive_int(run_id, "El run_id debe ser mayor que cero."))
    if suite is not None:
        clauses.append("r.suite = ?")
        params.append(_require_text(suite, "La suite de evaluacion es obligatoria."))
    if benchmark is not None:
        clauses.append("r.benchmark = ?")
        params.append(
            _require_text(benchmark, "El benchmark de evaluacion es obligatorio.")
        )
    if model is not None:
        clauses.append("r.model = ?")
        params.append(_require_text(model, "El modelo de evaluacion es obligatorio."))
    if status is not None:
        clauses.append("r.status = ?")
        params.append(_require_text(status, "El estado del run es obligatorio."))

    if not clauses:
        return "", params
    return "WHERE " + " AND ".join(clauses), params


def _require_text(value: str, message: str) -> str:
    clean_value = value.strip()
    if not clean_value:
        raise ValueError(message)
    return clean_value


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    clean_value = value.strip()
    return clean_value or None


def _require_positive_int(value: int, message: str) -> int:
    if value <= 0:
        raise ValueError(message)
    return value


def _require_non_negative_int(value: int, message: str) -> int:
    if value < 0:
        raise ValueError(message)
    return value


def _require_non_negative_float(value: float, message: str) -> float:
    if value < 0:
        raise ValueError(message)
    return float(value)


def _compute_pass_rate(passed_cases: int, case_count: int) -> float | None:
    if case_count <= 0:
        return None
    return round(passed_cases / case_count, 4)


def _round_optional(value: Any) -> float | None:
    if value is None:
        return None
    return round(float(value), 4)


def _dump_json_dict(payload: dict[str, Any] | None) -> str:
    return json.dumps(dict(payload or {}), ensure_ascii=False, sort_keys=True)


def _load_json_dict(payload: Any) -> dict[str, Any]:
    data = json.loads(str(payload))
    if not isinstance(data, dict):
        raise ValueError("El campo metadata_json debe contener un objeto JSON.")
    return data


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


__all__ = [
    "EvalAggregateSummary",
    "EvalCaseRecord",
    "EvalRunRecord",
    "EvalRunSummary",
    "EvalStore",
]
