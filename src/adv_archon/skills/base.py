"""Base class for ADV ARCHON skills."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillResult:
    success: bool
    output: str
    artifacts: dict[str, Any] = field(default_factory=dict)


class Skill(ABC):
    """Base class all skills must extend."""

    name: str = ""
    description: str = ""
    args_schema: dict[str, Any] = {}

    @abstractmethod
    def run(self, **kwargs: Any) -> SkillResult:
        """Execute the skill. kwargs are validated against args_schema."""
        ...

    def __repr__(self) -> str:
        return f"<Skill:{self.name}>"
