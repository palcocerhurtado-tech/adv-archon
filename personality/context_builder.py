from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class PersonalityPaths:
    core_identity_path: Path
    state_db_path: Path


def build_system_prompt(
    base_system_prompt: str,
    *,
    paths: PersonalityPaths,
    token_budget: int = 1200,
) -> str:
    """Build the effective system prompt without changing behavior for empty identity.

    FASE 2 intentionally avoids LLM-generated summaries. It reads a small, deterministic
    snapshot from SQLite so local models do not receive raw personality state.
    """
    _ensure_schema(paths.state_db_path)
    core_identity = _load_core_identity(paths.core_identity_path)
    identity_block = _render_core_identity(core_identity)
    state_block = _render_adaptive_state(paths.state_db_path)
    extra = "\n\n".join(block for block in (identity_block, state_block) if block)
    if not extra:
        return base_system_prompt
    return _truncate_to_budget(
        f"{base_system_prompt.rstrip()}\n\n{extra}",
        token_budget=token_budget,
    )


def _load_core_identity(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _render_core_identity(data: dict[str, Any]) -> str:
    name = str(data.get("name") or "").strip()
    tone = str(data.get("tone_baseline") or "").strip()
    values = [str(item).strip() for item in data.get("values", []) if str(item).strip()]
    hard_nos = [str(item).strip() for item in data.get("hard_nos", []) if str(item).strip()]
    self_reference = str(data.get("self_reference") or "").strip()

    lines: list[str] = []
    if name:
        lines.append(f"- Name: {name}")
    if tone:
        lines.append(f"- Tone baseline: {tone}")
    if values:
        lines.append("- Values: " + "; ".join(values[:8]))
    if hard_nos:
        lines.append("- Hard nos: " + "; ".join(hard_nos[:8]))
    if self_reference:
        lines.append(f"- Self-reference: {self_reference}")
    if not lines:
        return ""
    return "## Core Identity\n" + "\n".join(lines)


def _render_adaptive_state(db_path: Path) -> str:
    _ensure_schema(db_path)
    try:
        with sqlite3.connect(str(db_path)) as conn:
            preferences = conn.execute(
                "SELECT key, value FROM user_preferences ORDER BY updated_at DESC LIMIT 8"
            ).fetchall()
            patterns = conn.execute(
                """
                SELECT pattern_type, value
                FROM interaction_patterns
                ORDER BY weight DESC, last_seen DESC
                LIMIT 6
                """
            ).fetchall()
            events = conn.execute(
                """
                SELECT summary
                FROM significant_events
                ORDER BY importance DESC, timestamp DESC
                LIMIT 5
                """
            ).fetchall()
    except sqlite3.Error:
        return ""

    lines: list[str] = []
    if preferences:
        lines.append("User preferences:")
        lines.extend(f"- {key}: {value}" for key, value in preferences)
    if patterns:
        lines.append("Interaction patterns:")
        lines.extend(f"- {kind}: {value}" for kind, value in patterns)
    if events:
        lines.append("Significant events:")
        lines.extend(f"- {summary}" for (summary,) in events)
    if not lines:
        return ""
    return "## Adaptive State Summary\n" + "\n".join(lines)


def _ensure_schema(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS interaction_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type TEXT NOT NULL,
                value TEXT NOT NULL,
                weight REAL NOT NULL,
                last_seen TIMESTAMP NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS significant_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                importance INTEGER NOT NULL
            )
            """
        )


def _truncate_to_budget(text: str, *, token_budget: int) -> str:
    if token_budget <= 0:
        return text
    max_chars = token_budget * 4
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 80)].rstrip() + "\n\n[Personality context truncated.]"
