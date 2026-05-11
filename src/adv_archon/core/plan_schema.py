"""Plan-and-execute data model for ADV ARCHON."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class RiskLevel(StrEnum):
    LOW = "low"          # read-only, purely informational
    MEDIUM = "medium"    # network calls, temporary files
    HIGH = "high"        # file writes, git operations, installs
    CRITICAL = "critical"  # ~/.ssh, ~/.zshrc, destructive git, push to main


@dataclass
class Step:
    index: int
    intent: str
    tool: str
    arguments: dict[str, Any]
    risk: RiskLevel
    reversible: bool
    completed: bool = False
    skipped: bool = False
    result: str | None = None


@dataclass
class Plan:
    objective: str
    steps: list[Step]
    approved: bool = False
    aborted: bool = False

    def pending_steps(self) -> list[Step]:
        return [s for s in self.steps if not s.completed and not s.skipped]

    def summary(self) -> str:
        lines = [f"Objetivo: {self.objective}", ""]
        for s in self.steps:
            status = "✓" if s.completed else ("✗" if s.skipped else "·")
            risk_tag = f"[{s.risk.value.upper()}]"
            lines.append(f"  {status} Paso {s.index}: {s.intent} {risk_tag}")
        return "\n".join(lines)
