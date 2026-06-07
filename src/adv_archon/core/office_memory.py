from __future__ import annotations

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class OfficeDecision:
    id: int
    municipality: str
    step_code: str
    action: str
    label: str
    note: str
    source: str
    created_at: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "municipality": self.municipality,
            "step_code": self.step_code,
            "action": self.action,
            "label": self.label,
            "note": self.note,
            "source": self.source,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class MunicipalityPolicy:
    municipality: str
    validated_pgou: bool
    accepted_warnings: tuple[str, ...]
    excluded_steps: tuple[str, ...]
    repeated_steps: tuple[str, ...]
    decision_count: int

    def as_payload(self) -> dict[str, Any]:
        return {
            "municipality": self.municipality,
            "validated_pgou": self.validated_pgou,
            "accepted_warnings": list(self.accepted_warnings),
            "excluded_steps": list(self.excluded_steps),
            "repeated_steps": list(self.repeated_steps),
            "decision_count": self.decision_count,
        }


@dataclass(frozen=True, slots=True)
class OfficeMemorySnapshot:
    municipalities: tuple[str, ...]
    recurring_warnings: tuple[str, ...]
    validated_decisions: int
    preferred_report_style: str
    policies: tuple[MunicipalityPolicy, ...]

    def policy_for(self, municipality: str) -> MunicipalityPolicy | None:
        normalized = _normalize_municipality(municipality)
        for policy in self.policies:
            if _normalize_municipality(policy.municipality) == normalized:
                return policy
        return None

    def as_payload(self) -> dict[str, Any]:
        return {
            "municipalities": list(self.municipalities),
            "recurring_warnings": list(self.recurring_warnings),
            "validated_decisions": self.validated_decisions,
            "preferred_report_style": self.preferred_report_style,
            "policies": [policy.as_payload() for policy in self.policies],
        }


class OfficeMemoryStore:
    """Local SQLite memory for despacho-level review criteria.

    This is not a legal authority. It records how the architecture office has reviewed
    previous expediente steps so Autopilot can surface recurring criteria instead of
    behaving as a blank slate on every dossier.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def close(self) -> None:
        self._conn.close()

    def _migrate(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS office_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                municipality TEXT NOT NULL DEFAULT '',
                step_code TEXT NOT NULL,
                action TEXT NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'architect',
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_office_decisions_municipality_step
            ON office_decisions(municipality, step_code, created_at DESC)
            """
        )
        self._conn.commit()

    def record_step_decision(
        self,
        *,
        municipality: str,
        step_code: str,
        action: str,
        label: str = "",
        note: str = "",
        source: str = "architect",
        created_at: str | None = None,
    ) -> OfficeDecision:
        timestamp = created_at or datetime.now(UTC).isoformat(timespec="seconds")
        self._conn.execute(
            """
            INSERT INTO office_decisions
              (municipality, step_code, action, label, note, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                municipality.strip(),
                step_code.strip(),
                _normalize_action(action),
                label.strip(),
                note.strip(),
                source.strip() or "architect",
                timestamp,
            ),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT * FROM office_decisions WHERE id = last_insert_rowid()"
        ).fetchone()
        return self._row_to_decision(row)

    def latest_decisions(
        self,
        *,
        municipality: str = "",
        limit: int = 30,
    ) -> tuple[OfficeDecision, ...]:
        if municipality.strip():
            rows = self._conn.execute(
                """
                SELECT * FROM office_decisions
                WHERE municipality = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (municipality.strip(), max(1, limit)),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT * FROM office_decisions
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (max(1, limit),),
            ).fetchall()
        return tuple(self._row_to_decision(row) for row in rows)

    def snapshot(self) -> OfficeMemorySnapshot:
        rows = self._conn.execute(
            "SELECT * FROM office_decisions ORDER BY created_at DESC, id DESC"
        ).fetchall()
        decisions = [self._row_to_decision(row) for row in rows]
        return build_office_memory_snapshot(decisions)

    @staticmethod
    def _row_to_decision(row: sqlite3.Row) -> OfficeDecision:
        return OfficeDecision(
            id=int(row["id"]),
            municipality=str(row["municipality"] or ""),
            step_code=str(row["step_code"] or ""),
            action=str(row["action"] or ""),
            label=str(row["label"] or ""),
            note=str(row["note"] or ""),
            source=str(row["source"] or ""),
            created_at=str(row["created_at"] or ""),
        )


def build_office_memory_snapshot(
    decisions: list[OfficeDecision] | tuple[OfficeDecision, ...],
) -> OfficeMemorySnapshot:
    municipalities: Counter[str] = Counter()
    accepted_warnings: Counter[str] = Counter()
    validated_decisions = 0
    grouped: dict[str, list[OfficeDecision]] = {}
    for decision in decisions:
        municipality = decision.municipality.strip()
        if municipality:
            municipalities[municipality] += 1
            grouped.setdefault(_normalize_municipality(municipality), []).append(decision)
        if decision.action == "validated":
            validated_decisions += 1
        if decision.action == "accepted_warning":
            accepted_warnings[decision.step_code] += 1

    policies = tuple(
        _policy_from_decisions(items)
        for _, items in sorted(
            grouped.items(),
            key=lambda item: (-len(item[1]), item[0]),
        )
    )
    return OfficeMemorySnapshot(
        municipalities=tuple(name for name, _ in municipalities.most_common(8)),
        recurring_warnings=tuple(name for name, _ in accepted_warnings.most_common(8)),
        validated_decisions=validated_decisions,
        preferred_report_style=_preferred_report_style(decisions),
        policies=policies,
    )


def build_office_memory_context(snapshot: OfficeMemorySnapshot) -> str:
    lines = [
        "## Office Memory",
        f"- Preferred report style: {snapshot.preferred_report_style}",
        f"- Validated decisions: {snapshot.validated_decisions}",
    ]
    if snapshot.municipalities:
        lines.append("- Frequent municipalities: " + "; ".join(snapshot.municipalities[:8]))
    if snapshot.recurring_warnings:
        lines.append("- Recurring accepted warnings: " + "; ".join(snapshot.recurring_warnings[:8]))
    for policy in snapshot.policies[:5]:
        chunks = [policy.municipality]
        if policy.validated_pgou:
            chunks.append("PGOU validated by office review")
        if policy.accepted_warnings:
            chunks.append("accepted warnings=" + ", ".join(policy.accepted_warnings[:4]))
        if policy.excluded_steps:
            chunks.append("excluded=" + ", ".join(policy.excluded_steps[:4]))
        if policy.repeated_steps:
            chunks.append("repeat=" + ", ".join(policy.repeated_steps[:4]))
        lines.append("- Policy: " + " | ".join(chunks))
    return "\n".join(lines)


def snapshot_from_expedientes(expedientes: list[Any] | tuple[Any, ...]) -> OfficeMemorySnapshot:
    decisions: list[OfficeDecision] = []
    next_id = 1
    for expediente in expedientes:
        municipality = str(getattr(expediente, "municipality", "") or "").strip()
        raw_reviews = str(getattr(expediente, "agent_step_reviews", "") or "")
        if not raw_reviews.strip():
            continue
        try:
            reviews = json.loads(raw_reviews)
        except (TypeError, ValueError):
            continue
        if not isinstance(reviews, dict):
            continue
        for step_code, raw in reviews.items():
            if not isinstance(raw, dict):
                continue
            action = str(raw.get("status") or "").strip()
            if not action or action == "pending":
                continue
            decisions.append(
                OfficeDecision(
                    id=next_id,
                    municipality=municipality,
                    step_code=str(step_code),
                    action=action,
                    label=str(raw.get("label") or ""),
                    note=str(raw.get("note") or ""),
                    source="expediente",
                    created_at=str(raw.get("updated_at") or ""),
                )
            )
            next_id += 1
    return build_office_memory_snapshot(decisions)


def _policy_from_decisions(decisions: list[OfficeDecision]) -> MunicipalityPolicy:
    municipality = next((item.municipality for item in decisions if item.municipality), "")
    accepted = tuple(
        code
        for code, _ in Counter(
            item.step_code for item in decisions if item.action == "accepted_warning"
        ).most_common(8)
    )
    excluded = tuple(
        code
        for code, _ in Counter(
            item.step_code for item in decisions if item.action == "excluded"
        ).most_common(8)
    )
    repeated = tuple(
        code
        for code, _ in Counter(
            item.step_code for item in decisions if item.action == "requested_repeat"
        ).most_common(8)
    )
    validated_pgou = any(
        item.step_code == "pgou-normativa"
        and item.action in {"validated", "accepted_warning", "included"}
        for item in decisions
    )
    return MunicipalityPolicy(
        municipality=municipality,
        validated_pgou=validated_pgou,
        accepted_warnings=accepted,
        excluded_steps=excluded,
        repeated_steps=repeated,
        decision_count=len(decisions),
    )


def _preferred_report_style(
    decisions: list[OfficeDecision] | tuple[OfficeDecision, ...],
) -> str:
    if any(item.action == "accepted_warning" for item in decisions):
        return (
            "Informe preliminar de viabilidad urbanistica con advertencias reforzadas "
            "y trazabilidad de decisiones del arquitecto."
        )
    if any(item.action == "excluded" for item in decisions):
        return (
            "Informe ejecutivo compacto, excluyendo conclusiones no defendibles y "
            "manteniendo anexo tecnico trazable."
        )
    return "Informe preliminar de viabilidad urbanistica con trazabilidad fuerte."


def _normalize_municipality(value: str) -> str:
    return " ".join(value.casefold().strip().split())


def _normalize_action(value: str) -> str:
    normalized = value.strip().replace("-", "_")
    return {
        "validate": "validated",
        "accept_warning": "accepted_warning",
        "accepted_warning": "accepted_warning",
        "repeat": "requested_repeat",
        "requested_repeat": "requested_repeat",
        "include": "included",
        "included": "included",
        "exclude": "excluded",
        "excluded": "excluded",
    }.get(normalized, normalized)


__all__ = [
    "MunicipalityPolicy",
    "OfficeDecision",
    "OfficeMemorySnapshot",
    "OfficeMemoryStore",
    "build_office_memory_context",
    "build_office_memory_snapshot",
    "snapshot_from_expedientes",
]
