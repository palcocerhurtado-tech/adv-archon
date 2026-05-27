from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ExportResult:
    output_path: Path
    examples_exported: int


class FeedbackStore:
    """SQLite store for compliance examples that can feed future local fine-tuning."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path.expanduser()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    def _migrate(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS compliance_examples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                example_hash TEXT NOT NULL UNIQUE,
                expediente_id TEXT NOT NULL DEFAULT '',
                municipality TEXT NOT NULL,
                plan_summary TEXT NOT NULL,
                site_context TEXT NOT NULL,
                analysis TEXT NOT NULL,
                judge_score INTEGER,
                judge_flags TEXT NOT NULL DEFAULT '[]',
                approved_by_user INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            """
        )
        existing = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(compliance_examples)")
        }
        columns = {
            "example_hash": "TEXT NOT NULL DEFAULT ''",
            "expediente_id": "TEXT NOT NULL DEFAULT ''",
            "municipality": "TEXT NOT NULL DEFAULT ''",
            "plan_summary": "TEXT NOT NULL DEFAULT ''",
            "site_context": "TEXT NOT NULL DEFAULT ''",
            "analysis": "TEXT NOT NULL DEFAULT ''",
            "judge_score": "INTEGER",
            "judge_flags": "TEXT NOT NULL DEFAULT '[]'",
            "approved_by_user": "INTEGER NOT NULL DEFAULT 0",
            "created_at": "TEXT NOT NULL DEFAULT ''",
        }
        for name, definition in columns.items():
            if name not in existing:
                self._conn.execute(
                    f"ALTER TABLE compliance_examples ADD COLUMN {name} {definition}"
                )
        self._conn.commit()

    def add_from_expediente(
        self,
        expediente: Any,
        *,
        approved_by_user: bool | None = None,
    ) -> int:
        raw_analysis = getattr(expediente, "analysis_result", "")
        analysis = _loads_json(raw_analysis)
        judge_result = _loads_json(getattr(expediente, "quality_result", ""))
        if not judge_result and isinstance(analysis, dict):
            raw_quality = analysis.get("quality")
            judge_result = raw_quality if isinstance(raw_quality, dict) else {}
        analysis_payload: dict[str, Any] | str = analysis if analysis else str(raw_analysis or "")
        return self.add_example(
            expediente=expediente,
            analysis=analysis_payload,
            judge_result=judge_result,
            approved_by_user=approved_by_user,
        )

    def add_example(
        self,
        expediente: Any,
        analysis: dict[str, Any] | str,
        judge_result: dict[str, Any],
        approved_by_user: bool | None = None,
    ) -> int:
        municipality = str(getattr(expediente, "municipality", "") or "")
        plan_summary = _build_plan_summary(expediente)
        site_context = str(getattr(expediente, "site_context", "") or "")
        analysis_text = _normalise_json_text(analysis)
        score = _score_from_judge(judge_result)
        flags = _flags_from_judge(judge_result)
        approved = (
            (score is not None and score >= 70)
            if approved_by_user is None
            else approved_by_user
        )
        example_hash = _example_hash(
            municipality=municipality,
            plan_summary=plan_summary,
            site_context=site_context,
            analysis=analysis_text,
        )
        now = datetime.now(UTC).isoformat()
        self._conn.execute(
            """
            INSERT INTO compliance_examples (
                example_hash, expediente_id, municipality, plan_summary,
                site_context, analysis, judge_score, judge_flags,
                approved_by_user, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(example_hash) DO UPDATE SET
                judge_score = excluded.judge_score,
                judge_flags = excluded.judge_flags,
                approved_by_user = MAX(
                    compliance_examples.approved_by_user,
                    excluded.approved_by_user
                )
            """,
            (
                example_hash,
                str(getattr(expediente, "id", "") or ""),
                municipality,
                plan_summary,
                site_context,
                analysis_text,
                score,
                json.dumps(flags, ensure_ascii=False),
                1 if approved else 0,
                now,
            ),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT id FROM compliance_examples WHERE example_hash = ?",
            (example_hash,),
        ).fetchone()
        return int(row["id"]) if row else 0

    def export_alpaca(self, output_path: Path) -> ExportResult:
        output_path = output_path.expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        rows = self._conn.execute(
            """
            SELECT municipality, plan_summary, site_context, analysis
            FROM compliance_examples
            WHERE approved_by_user = 1 AND COALESCE(judge_score, 0) >= 70
            ORDER BY created_at ASC, id ASC
            """
        ).fetchall()
        with output_path.open("w", encoding="utf-8") as handle:
            for row in rows:
                payload = {
                    "instruction": "Analiza el cumplimiento urbanístico:",
                    "input": _alpaca_input(row),
                    "output": row["analysis"],
                }
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return ExportResult(output_path=output_path, examples_exported=len(rows))

    def count(self, *, approved_only: bool = False) -> int:
        where = "WHERE approved_by_user = 1" if approved_only else ""
        row = self._conn.execute(
            f"SELECT COUNT(*) AS total FROM compliance_examples {where}"
        ).fetchone()
        return int(row["total"] or 0) if row else 0


def _build_plan_summary(expediente: Any) -> str:
    lines = [
        f"Título: {getattr(expediente, 'title', '')}",
        f"Tipo de actuación: {getattr(expediente, 'case_type', '')}",
        f"Dirección: {getattr(expediente, 'address', '')}",
        f"Municipio: {getattr(expediente, 'municipality', '')}",
        f"Provincia: {getattr(expediente, 'province', '')}",
        f"Referencia catastral: {getattr(expediente, 'cadastral_ref', '')}",
        f"Plano: {Path(str(getattr(expediente, 'plan_path', '') or '')).name}",
        f"Notas: {getattr(expediente, 'notes', '')}",
    ]
    return "\n".join(line for line in lines if not line.endswith(": "))


def _normalise_json_text(value: dict[str, Any] | str) -> str:
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value or "")


def _score_from_judge(judge_result: dict[str, Any]) -> int | None:
    raw = judge_result.get("score")
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        return max(0, min(100, int(raw)))
    except (TypeError, ValueError):
        return None


def _flags_from_judge(judge_result: dict[str, Any]) -> list[str]:
    raw = judge_result.get("flags")
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw]


def _loads_json(text: object) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _example_hash(
    *,
    municipality: str,
    plan_summary: str,
    site_context: str,
    analysis: str,
) -> str:
    payload = json.dumps(
        {
            "municipality": municipality,
            "plan_summary": plan_summary,
            "site_context": site_context,
            "analysis": analysis,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _alpaca_input(row: sqlite3.Row) -> str:
    return "\n\n".join(
        part
        for part in (
            f"MUNICIPIO: {row['municipality']}",
            f"RESUMEN DEL EXPEDIENTE:\n{row['plan_summary']}",
            f"CONTEXTO OFICIAL:\n{row['site_context']}",
        )
        if part.strip()
    )


__all__ = ["ExportResult", "FeedbackStore"]
